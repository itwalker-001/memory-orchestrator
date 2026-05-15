export const BASE = '/api'

export function apiFetch(url, opts = {}) {
  return fetch(url, opts)
}

export async function apiJSON(url, opts = {}) {
  const r = await apiFetch(url, opts)
  if (!r.ok) {
    const err = await r.json().catch(() => ({}))
    throw new Error(err.detail || r.statusText)
  }
  return r.json()
}
