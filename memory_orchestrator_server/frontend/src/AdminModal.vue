<script setup>
import { ref, onMounted } from 'vue'
import { BASE, apiFetch } from './api.js'
import enLocale from './locales/en.json'
import zhLocale from './locales/zh.json'
import IconLock from './icons/IconLock.svg'
import IconPlus from './icons/IconPlus.svg'
import IconClose from './icons/IconClose.svg'
import IconSync from './icons/IconSync.svg'
import IconTrash from './icons/IconTrash.svg'

const props = defineProps({
  open: { type: Boolean, required: true },
  lang: { type: String, default: 'en' },
})
const emit = defineEmits(['update:open', 'require-login'])

function t(key) { return ({ en: enLocale, zh: zhLocale }[props.lang] || enLocale)[key] ?? key }
function close() { emit('update:open', false) }

function relTime(iso) {
  if (!iso) return '—'
  const diff = (Date.now() - new Date(iso).getTime()) / 1000
  if (diff < 60) return 'just now'
  if (diff < 3600) return Math.floor(diff / 60) + 'm'
  if (diff < 86400) return Math.floor(diff / 3600) + 'h'
  if (diff < 86400 * 7) return Math.floor(diff / 86400) + 'd'
  if (diff < 86400 * 30) return Math.floor(diff / (86400 * 7)) + 'w'
  return Math.floor(diff / (86400 * 30)) + 'mo'
}

const copied = ref(null)
async function copy(text) {
  await navigator.clipboard.writeText(text)
  copied.value = text
  setTimeout(() => { copied.value = null }, 1500)
}

// ── State ──
const adminTokens = ref([])
const adminLoading = ref(false)
const adminCreateOpen = ref(false)
const adminNewKind = ref('ui_admin')
const adminNewName = ref('')
const adminCreating = ref(false)
const adminCreatedToken = ref('')
const tokenActionTarget = ref(null)
const isTokenActioning = ref(false)

// ── API ──
async function load() {
  adminLoading.value = true
  try {
    const r = await apiFetch(`${BASE}/tokens`)
    if (r.status === 401) { emit('require-login'); return }
    adminTokens.value = await r.json()
  } finally {
    adminLoading.value = false
  }
}

async function adminCreate() {
  if (!adminNewName.value) return
  adminCreating.value = true
  try {
    const body = { kind: adminNewKind.value, name: adminNewName.value }
    const r = await apiFetch(`${BASE}/tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) return
    const data = await r.json()
    adminCreatedToken.value = data.token
    adminNewName.value = ''
    adminCreateOpen.value = false
    await load()
  } finally {
    adminCreating.value = false
  }
}

async function adminToggle(tok) {
  await apiFetch(`${BASE}/tokens/${tok.id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled: !tok.enabled }),
  })
  await load()
}

function openTokenAction(tok, action) {
  tokenActionTarget.value = { tok, action }
}

async function confirmTokenAction() {
  if (!tokenActionTarget.value) return
  const { tok, action } = tokenActionTarget.value
  isTokenActioning.value = true
  try {
    if (action === 'reset') {
      const r = await apiFetch(`${BASE}/tokens/${tok.id}/reset`, { method: 'POST' })
      if (r.ok) {
        const data = await r.json()
        adminCreatedToken.value = data.token
        await load()
      }
    } else {
      await apiFetch(`${BASE}/tokens/${tok.id}`, { method: 'DELETE' })
      await load()
    }
  } finally {
    isTokenActioning.value = false
    tokenActionTarget.value = null
  }
}

onMounted(() => { load() })
defineExpose({ load })
</script>

<template>
  <!-- ── API Tokens modal ── -->
  <div v-if="open" class="modal-overlay" @click.self="close">
    <div class="modal admin-modal">
      <div class="modal-header">
        <span class="modal-title">
          <IconLock width="13" height="13" style="margin-right:6px;vertical-align:-2px" />
          {{ t('API Tokens') }}
        </span>
        <div style="display:flex;align-items:center;gap:8px">
          <button class="btn-new admin-create-toggle" @click="adminCreateOpen = !adminCreateOpen">
            <IconPlus width="11" height="11" />
            {{ t('New') }}
          </button>
          <button class="modal-close" @click="close">
            <IconClose width="12" height="12" />
          </button>
        </div>
      </div>

      <div class="admin-modal-body">
        <div v-if="adminCreateOpen" class="admin-create-form">
          <select v-model="adminNewKind" class="admin-select">
            <option value="ui_admin">ui_admin</option>
            <option value="mcp_client">mcp_client</option>
          </select>
          <input v-model="adminNewName" class="admin-input" :placeholder="t('Name…')" @keydown.enter="adminCreate" />
          <button class="btn-save admin-create-btn" :disabled="!adminNewName || adminCreating" @click="adminCreate">
            {{ adminCreating ? t('Saving…') : t('Create') }}
          </button>
          <button class="btn-cancel" @click="adminCreateOpen = false">{{ t('Cancel') }}</button>
        </div>

        <div v-if="adminCreatedToken" class="admin-new-token-banner">
          <span class="admin-new-token-label">{{ t('Token value (save this — shown only once):') }}</span>
          <code class="admin-new-token-value copyable" @click="copy(adminCreatedToken)" :title="t('Click to copy')">{{ adminCreatedToken }}</code>
          <span class="copy-hint" v-if="copied === adminCreatedToken">{{ t('Copied') }}</span>
          <button class="btn-cancel admin-dismiss" @click="adminCreatedToken = ''">{{ t('Close') }}</button>
        </div>

        <div v-if="adminLoading" class="admin-empty">{{ t('Loading…') }}</div>
        <div v-else-if="!adminTokens.length" class="admin-empty">{{ t('No tokens yet.') }}</div>
        <table v-else class="admin-table">
          <thead>
            <tr>
              <th>{{ t('Kind') }}</th>
              <th>{{ t('Name') }}</th>
              <th>{{ t('Status') }}</th>
              <th>{{ t('Created') }}</th>
              <th>{{ t('Last used') }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="tok in adminTokens" :key="tok.id" :class="{ 'admin-row-disabled': !tok.enabled }">
              <td><span :class="['admin-kind-badge', tok.kind === 'ui_admin' ? 'admin-kind-ui' : 'admin-kind-mcp']">{{ tok.kind }}</span></td>
              <td class="admin-name-cell">{{ tok.name }}</td>
              <td>
                <button
                  :class="['admin-toggle', tok.enabled ? 'admin-toggle-on' : 'admin-toggle-off']"
                  @click="adminToggle(tok)"
                  :title="tok.enabled ? t('Disable') : t('Enable')"
                >
                  <span class="admin-toggle-knob"></span>
                </button>
                <span class="admin-status-text">{{ tok.enabled ? t('Enabled') : t('Disabled') }}</span>
              </td>
              <td class="admin-date">{{ relTime(tok.created_at) }}</td>
              <td class="admin-date">{{ tok.last_used_at ? relTime(tok.last_used_at) : '—' }}</td>
              <td class="admin-actions-cell">
                <button class="btn-cancel admin-reset" @click="openTokenAction(tok, 'reset')" :title="t('Reset')">
                  <IconSync width="11" height="11" />
                  {{ t('Reset') }}
                </button>
                <button class="btn-token-revoke admin-revoke" @click="openTokenAction(tok, 'revoke')" :title="t('Revoke')">
                  <IconTrash width="11" height="11" />
                  {{ t('Revoke') }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ── Token action confirm ── -->
  <div v-if="tokenActionTarget" class="modal-overlay" @click.self="tokenActionTarget = null">
    <div class="modal modal-sm">
      <div class="modal-header">
        <span class="modal-title">{{ tokenActionTarget.action === 'reset' ? t('Reset token') : t('Revoke token') }}</span>
        <button class="modal-close" @click="tokenActionTarget = null">
          <IconClose width="12" height="12" />
        </button>
      </div>
      <div class="modal-body delete-modal-body">
        <IconSync v-if="tokenActionTarget.action === 'reset'" width="32" height="32" class="delete-icon" style="color:var(--accent)" />
        <IconTrash v-else width="32" height="32" class="delete-icon" />
        <p class="delete-confirm-text"><strong>{{ tokenActionTarget.tok.name }}</strong></p>
        <p class="delete-confirm-sub">{{ tokenActionTarget.action === 'reset' ? t('Reset token desc') : t('Revoke token desc') }}</p>
      </div>
      <div class="modal-footer">
        <button class="btn-cancel" @click="tokenActionTarget = null">{{ t('Cancel') }}</button>
        <button :class="tokenActionTarget.action === 'reset' ? 'btn-save' : 'btn-danger'" @click="confirmTokenAction" :disabled="isTokenActioning">
          {{ isTokenActioning ? t('Processing…') : (tokenActionTarget.action === 'reset' ? t('Reset') : t('Revoke')) }}
        </button>
      </div>
    </div>
  </div>
</template>

<style>
/* ── Admin modal ── */
.admin-modal {
  width: min(900px, 96vw);
  max-width: min(900px, 96vw);
  display: flex; flex-direction: column;
}
.admin-modal-body { overflow: visible; padding: 0; }
.admin-create-form {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; border-bottom: 1px solid var(--border-subtle);
  background: var(--bg-secondary);
}
.admin-select, .admin-input {
  background: var(--surface-2); color: var(--text-primary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  padding: 6px 10px; font-size: 12px; outline: none;
  transition: border-color var(--transition);
}
.admin-select:focus, .admin-input:focus { border-color: var(--accent); }
.admin-input { flex: 1; }
.admin-create-btn { padding: 6px 14px; font-size: 12px; }
.admin-new-token-banner {
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  padding: 10px 16px; border-bottom: 1px solid var(--border-subtle);
  background: var(--green-dim); border-left: 3px solid var(--green);
}
.admin-new-token-label { font-size: 11px; color: var(--text-muted); white-space: nowrap; }
.admin-new-token-value {
  font-family: ui-monospace, monospace; font-size: 12px;
  background: var(--surface); border: 1px solid var(--border);
  padding: 3px 8px; border-radius: var(--radius-sm);
  color: var(--text-primary); word-break: break-all;
}
.admin-dismiss { padding: 4px 10px; font-size: 11px; margin-left: auto; }
.admin-table {
  width: 100%; border-collapse: collapse; font-size: 12px;
  table-layout: fixed;
}
.admin-table th {
  padding: 8px 14px; text-align: left;
  font-size: 10px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--text-muted); border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-panel);
}
.admin-table td {
  padding: 10px 14px; border-bottom: 1px solid var(--border-subtle);
  color: var(--text-primary); vertical-align: middle;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.admin-table tr:last-child td { border-bottom: none; }
.admin-table tr:hover td { background: var(--row-hover); }
.admin-table th:nth-child(1), .admin-table td:nth-child(1) { width: 110px; }
.admin-table th:nth-child(2), .admin-table td:nth-child(2) { width: auto; }
.admin-table th:nth-child(3), .admin-table td:nth-child(3) { width: 120px; white-space: nowrap; }
.admin-table th:nth-child(4), .admin-table td:nth-child(4) { width: 80px; }
.admin-table th:nth-child(5), .admin-table td:nth-child(5) { width: 90px; }
.admin-table th:nth-child(6), .admin-table td:nth-child(6) { width: 180px; white-space: nowrap; }
.admin-row-disabled td { opacity: 0.55; }
.admin-kind-badge {
  display: inline-block; padding: 2px 8px; border-radius: 20px;
  font-size: 10px; font-weight: 700; letter-spacing: 0.04em;
  font-family: ui-monospace, monospace;
}
.admin-kind-ui  { background: var(--blue-dim); color: var(--blue); border: 1px solid var(--blue-border); }
.admin-kind-mcp { background: var(--green-dim); color: var(--green); border: 1px solid var(--green-border); }
.admin-name-cell { max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; word-break: break-all; }
.admin-toggle {
  position: relative; display: inline-flex; align-items: center;
  width: 32px; height: 18px; border: none; border-radius: 18px;
  cursor: pointer; transition: background 0.2s; flex-shrink: 0;
  vertical-align: middle;
}
.admin-toggle-on  { background: var(--green); }
.admin-toggle-off { background: var(--border); }
.admin-toggle-knob {
  position: absolute; width: 12px; height: 12px; border-radius: 50%;
  background: #fff; transition: transform 0.2s; top: 3px; left: 3px;
  pointer-events: none;
}
.admin-toggle-on .admin-toggle-knob  { transform: translateX(14px); }
.admin-toggle-off .admin-toggle-knob { transform: translateX(0); }
.admin-status-text { margin-left: 7px; font-size: 11px; color: var(--text-muted); vertical-align: middle; }
.admin-date { color: var(--text-muted); font-size: 11px; white-space: nowrap; }
.admin-actions-cell { white-space: nowrap; }
.admin-reset,
.admin-revoke { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; padding: 4px 10px; opacity: 1; }
.btn-token-revoke {
  background: none; cursor: pointer;
  border: 1px solid rgba(207,34,46,0.3); border-radius: var(--radius-sm);
  color: var(--red);
  transition: background var(--transition), border-color var(--transition);
}
.btn-token-revoke:hover { background: var(--red-dim); border-color: rgba(207,34,46,0.55); }
[data-theme="dark"] .btn-token-revoke { border-color: rgba(248,81,73,0.25); }
[data-theme="dark"] .btn-token-revoke:hover { border-color: rgba(248,81,73,0.45); }
.admin-empty { padding: 24px; text-align: center; color: var(--text-muted); font-size: 13px; }
</style>
