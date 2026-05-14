<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from './AppHeader.vue'
import { BASE, apiFetch } from './api.js'
import enLocale from './locales/en.json'
import zhLocale from './locales/zh.json'

const router = useRouter()

// ── Theme / lang ──
const storedTheme = localStorage.getItem('mo-theme')
const isDark = ref(storedTheme ? storedTheme === 'dark' : true)
function toggleTheme() {
  isDark.value = !isDark.value
  localStorage.setItem('mo-theme', isDark.value ? 'dark' : 'light')
  document.documentElement.setAttribute('data-theme', isDark.value ? 'dark' : 'light')
}
const lang = ref(localStorage.getItem('mo-lang') || 'en')
function toggleLang() { lang.value = lang.value === 'en' ? 'zh' : 'en'; localStorage.setItem('mo-lang', lang.value) }
function t(key) { return ({ en: enLocale, zh: zhLocale }[lang.value] || enLocale)[key] ?? key }

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
const adminNewKind = ref('mcp_client')
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
    if (r.status === 401) { router.push('/memories'); return }
    adminTokens.value = await r.json()
  } finally {
    adminLoading.value = false
  }
}

async function adminCreate() {
  if (!adminNewName.value) return
  adminCreating.value = true
  try {
    const r = await apiFetch(`${BASE}/tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: adminNewKind.value, name: adminNewName.value }),
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

function openTokenAction(tok, action) { tokenActionTarget.value = { tok, action } }

async function confirmTokenAction() {
  if (!tokenActionTarget.value) return
  const { tok, action } = tokenActionTarget.value
  isTokenActioning.value = true
  try {
    if (action === 'reset') {
      const r = await apiFetch(`${BASE}/tokens/${tok.id}/reset`, { method: 'POST' })
      if (r.ok) { const data = await r.json(); adminCreatedToken.value = data.token; await load() }
    } else {
      await apiFetch(`${BASE}/tokens/${tok.id}`, { method: 'DELETE' })
      await load()
    }
  } finally {
    isTokenActioning.value = false
    tokenActionTarget.value = null
  }
}

async function logout() {
  await fetch(`${BASE}/logout`, { method: 'POST' })
  router.push('/memories')
}

onMounted(() => { load() })
</script>

<template>
  <div class="tp-app">
    <AppHeader :isDark="isDark" :lang="lang" :loginOpen="false"
      @toggle-theme="toggleTheme" @toggle-lang="toggleLang"
      @open-settings="router.push('/settings')" @open-admin="() => {}" @logout="logout">
      <template #nav>
        <router-link to="/memories">← {{ t('Memories') }}</router-link>
      </template>
    </AppHeader>

    <div class="tp-body">
      <div class="tp-card">
        <div class="tp-card-header">
          <span class="tp-card-title">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;vertical-align:-2px"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
            {{ t('API Tokens') }}
          </span>
          <button class="btn-new" @click="adminCreateOpen = !adminCreateOpen">
            <svg width="11" height="11" viewBox="0 0 12 12" fill="none"><line x1="6" y1="1" x2="6" y2="11" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/><line x1="1" y1="6" x2="11" y2="6" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg>
            {{ t('New') }}
          </button>
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
                  <button :class="['admin-toggle', tok.enabled ? 'admin-toggle-on' : 'admin-toggle-off']"
                    @click="adminToggle(tok)" :title="tok.enabled ? t('Disable') : t('Enable')">
                    <span class="admin-toggle-knob"></span>
                  </button>
                  <span class="admin-status-text">{{ tok.enabled ? t('Enabled') : t('Disabled') }}</span>
                </td>
                <td class="admin-date">{{ relTime(tok.created_at) }}</td>
                <td class="admin-date">{{ tok.last_used_at ? relTime(tok.last_used_at) : '—' }}</td>
                <td class="admin-actions-cell">
                  <button class="btn-cancel admin-reset" @click="openTokenAction(tok, 'reset')" :title="t('Reset')">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10"/><path d="M20.5 15a9 9 0 0 1-14.9 3.4L1 14"/></svg>
                    {{ t('Reset') }}
                  </button>
                  <button class="btn-token-revoke admin-revoke" @click="openTokenAction(tok, 'revoke')" :title="t('Revoke')">
                    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
                    {{ t('Revoke') }}
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Token action confirm -->
    <Teleport to="body">
      <div v-if="tokenActionTarget" class="modal-overlay" @click.self="tokenActionTarget = null">
        <div class="modal modal-sm">
          <div class="modal-header">
            <span class="modal-title">{{ tokenActionTarget.action === 'reset' ? t('Reset token') : t('Revoke token') }}</span>
            <button class="modal-close" @click="tokenActionTarget = null">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
          <div class="modal-body delete-modal-body">
            <svg v-if="tokenActionTarget.action === 'reset'" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="delete-icon" style="color:var(--accent)">
              <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/><path d="M3.5 9a9 9 0 0 1 14.9-3.4L23 10"/><path d="M20.5 15a9 9 0 0 1-14.9 3.4L1 14"/>
            </svg>
            <svg v-else width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="delete-icon">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
            </svg>
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
    </Teleport>
  </div>
</template>

<style scoped>
.tp-app {
  width: 100%; min-height: 100svh;
  display: flex; flex-direction: column;
  box-sizing: border-box;
  padding: 12px;
  gap: 12px;
}
.tp-body {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 8px;
}
.tp-card {
  width: min(900px, 100%);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 24px var(--shadow);
  overflow: hidden;
}
.tp-card-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--border-subtle);
  background: var(--surface-panel);
}
.tp-card-title {
  display: flex; align-items: center;
  font-size: 13px; font-weight: 600; color: var(--text-primary);
}
</style>
