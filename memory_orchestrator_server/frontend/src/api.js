import axios from 'axios'
import { useLocale } from './useLocale.js'

const { t } = useLocale()

// All API routes are served under /api. Keep this internal to the module — callers
// pass root-relative paths like apiJSON('/memories'), not the prefixed URL.
const API_BASE = '/api'

// ── Handlers injected from the Vue layer ────────────────────────────────────────
// naive-ui message can only be created inside a component (useMessage), so the app
// injects the toast + 401 handlers here at runtime.
let _onError = null   // (msg: string) => void
let _on401 = null     // () => void
let _pendingErrors = []   // errors emitted before the Vue layer wired _onError

export function setApiHandlers({ onError, on401 } = {}) {
  if (onError) {
    _onError = onError
    // Flush errors that occurred before the handler was registered. The first
    // page load fires API calls from a child component's onMounted, which runs
    // before the App-level handler registration — without this buffer those
    // early failures (e.g. backend down) would be lost and show nothing.
    if (_pendingErrors.length) {
      const buffered = _pendingErrors
      _pendingErrors = []
      buffered.forEach(msg => _onError(msg))
    }
  }
  if (on401) _on401 = on401
}

// Show an error toast, or buffer it until a handler is registered.
function emitError(msg) {
  if (_onError) _onError(msg)
  else _pendingErrors.push(msg)
}

async function messageFromError(error) {
  const resp = error?.response
  if (resp) {
    // resp.data may be a Blob (apiFetch) or parsed JSON (apiJSON).
    let data = resp.data
    if (data instanceof Blob) {
      try { data = JSON.parse(await data.text()) } catch { /* not json */ }
    }
    if (data) {
      if (typeof data === 'string') return data
      if (data.detail) return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    }
    return `Error ${resp.status}`
  }
  // No response → request never reached the server (down / connection refused / CORS).
  if (error?.code === 'ERR_NETWORK' || error?.message === 'Network Error') {
    return t('Cannot reach the server, please make sure the backend is running')
  }
  return error?.message || 'Request failed'
}

const http = axios.create({ baseURL: API_BASE, withCredentials: true })

http.interceptors.response.use(
  resp => resp,
  async error => {
    const status = error?.response?.status
    if (status === 401) {
      _on401 && _on401()
    } else if (!error?.response) {
      // Network error — no response at all (server down / connection refused when
      // hitting the backend directly). There is no status for callers to branch on,
      // so always surface it, even when skipErrorToast is set.
      emitError(await messageFromError(error))
    } else if (!error?.config?.skipErrorToast) {
      emitError(await messageFromError(error))
    }
    return Promise.reject(error)
  },
)

function buildConfig(url, opts = {}) {
  const cfg = {
    url,
    method: (opts.method || 'GET').toLowerCase(),
    headers: { ...(opts.headers || {}) },
  }
  if (opts.body !== undefined) {
    cfg.data = opts.body
    cfg.transformRequest = [d => d]   // already serialized by the caller
    if (typeof opts.body === 'string' && !hasHeader(cfg.headers, 'content-type')) {
      cfg.headers['Content-Type'] = 'application/json'
    }
  }
  return cfg
}

function hasHeader(headers, name) {
  return Object.keys(headers).some(k => k.toLowerCase() === name)
}

// ── fetch-compatible wrapper ────────────────────────────────────────────────────
// Reads the body as a Blob (like fetch defers parsing) and exposes ok/status/
// headers.get/json/text/blob. Never throws on HTTP errors and never pops a toast —
// callers branch on `.ok`/`.status` themselves. 401 still routes to the login modal.
export async function apiFetch(url, opts = {}) {
  const cfg = buildConfig(url, opts)
  cfg.responseType = 'blob'
  cfg.skipErrorToast = true
  cfg.validateStatus = () => true
  const resp = await http.request(cfg)
  if (resp.status === 401) _on401 && _on401()
  // apiFetch sets validateStatus:()=>true, so 5xx never reaches the response
  // interceptor. Surface server/gateway errors here (incl. the 502 the Vite dev
  // proxy returns when the backend is down) so callers don't fail silently.
  if (resp.status >= 500) {
    emitError(resp.status === 502
      ? t('Cannot reach the server, please make sure the backend is running')
      : t('Server error ({status})', { status: resp.status }))
  }
  const blob = resp.data
  return {
    ok: resp.status >= 200 && resp.status < 300,
    status: resp.status,
    headers: { get: n => resp.headers?.[String(n).toLowerCase()] ?? null },
    blob: async () => blob,
    text: async () => (blob && blob.text ? blob.text() : ''),
    json: async () => {
      const txt = blob && blob.text ? await blob.text() : ''
      return txt ? JSON.parse(txt) : {}
    },
  }
}

// ── JSON helper ─────────────────────────────────────────────────────────────────
// Resolves to parsed data on success; on error the interceptor pops a toast (unless
// opts.skipErrorToast) and the promise rejects so callers can still react.
export async function apiJSON(url, opts = {}) {
  const cfg = buildConfig(url, opts)
  cfg.skipErrorToast = opts.skipErrorToast
  const resp = await http.request(cfg)
  return resp.data
}

// Extract a human-readable message from an axios error, for inline form display.
export function errText(error) {
  const data = error?.response?.data
  if (data) {
    if (typeof data === 'string') return data
    if (data.detail) return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
  }
  return error?.message || 'Request failed'
}

// Copy text to the clipboard. navigator.clipboard only exists in secure contexts
// (HTTPS or localhost); when the UI is served over plain HTTP from a LAN IP it is
// undefined, so fall back to the legacy execCommand('copy') via a hidden textarea.
// Throws if both paths fail so callers can surface an error.
export async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(text)
    return
  }
  const ta = document.createElement('textarea')
  ta.value = text
  ta.style.position = 'fixed'
  ta.style.top = '-9999px'
  ta.setAttribute('readonly', '')
  document.body.appendChild(ta)
  ta.select()
  try {
    if (!document.execCommand('copy')) throw new Error('copy command rejected')
  } finally {
    document.body.removeChild(ta)
  }
}
