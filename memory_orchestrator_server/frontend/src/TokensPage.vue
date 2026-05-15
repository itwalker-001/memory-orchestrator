<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppHeader from './AppHeader.vue'
import { BASE, apiFetch } from './api.js'
import { useAppStore } from './stores/app.js'
import IconLock from './icons/IconLock.svg'
import IconPlus from './icons/IconPlus.svg'
import IconSync from './icons/IconSync.svg'
import IconTrash from './icons/IconTrash.svg'
import IconClose from './icons/IconClose.svg'

const router = useRouter()
const appStore = useAppStore()
const { isDark, lang } = storeToRefs(appStore)
const { t, toggleTheme, toggleLang } = appStore

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
const adminNewProjectId = ref('')
const adminCreating = ref(false)
const adminCreatedToken = ref('')
const tokenActionTarget = ref(null)
const isTokenActioning = ref(false)
const projects = ref([])

function projectName(projectId) {
  if (!projectId) return '—'
  const p = projects.value.find(p => p.id === projectId)
  return p ? (p.display_name || p.slug) : projectId.slice(0, 8) + '…'
}

// ── API ──
async function load() {
  adminLoading.value = true
  try {
    const [tokR, projR] = await Promise.all([
      apiFetch(`${BASE}/tokens`),
      apiFetch(`${BASE}/projects`),
    ])
    if (tokR.status === 401) { router.push('/memories'); return }
    adminTokens.value = await tokR.json()
    if (projR.ok) projects.value = await projR.json()
  } finally {
    adminLoading.value = false
  }
}

async function adminCreate() {
  if (!adminNewName.value) return
  if (adminNewKind.value === 'project_token' && !adminNewProjectId.value) return
  adminCreating.value = true
  try {
    const body = { kind: adminNewKind.value, name: adminNewName.value }
    if (adminNewKind.value === 'project_token') body.project_id = adminNewProjectId.value
    const r = await apiFetch(`${BASE}/tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!r.ok) return
    const data = await r.json()
    adminCreatedToken.value = data.token
    adminNewName.value = ''
    adminNewProjectId.value = ''
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
    <AppHeader :loginOpen="false"
      @open-settings="router.push('/settings')" @logout="logout">
      <template #nav>
        <router-link to="/memories">← {{ t('Memories') }}</router-link>
      </template>
    </AppHeader>

    <!-- Toolbar -->
    <div class="toolbar">
      <IconLock width="13" height="13" style="flex-shrink:0" />
      <span class="tp-title">{{ t('API Tokens') }}</span>
      <div class="toolbar-spacer" />
      <button class="btn-new" @click="adminCreateOpen = !adminCreateOpen">
        <IconPlus width="11" height="11" />
        {{ t('New') }}
      </button>
    </div>

    <!-- Create form -->
    <div v-if="adminCreateOpen" class="admin-create-form">
      <select v-model="adminNewKind" class="admin-select">
        <option value="ui_admin">ui_admin</option>
        <option value="project_token">project_token</option>
      </select>
      <select v-if="adminNewKind === 'project_token'" v-model="adminNewProjectId" class="admin-select">
        <option value="" disabled>{{ t('Select project…') }}</option>
        <option v-for="p in projects" :key="p.id" :value="p.id">{{ p.display_name || p.slug }}</option>
      </select>
      <input v-model="adminNewName" class="admin-input" :placeholder="t('Name…')" @keydown.enter="adminCreate" />
      <button class="btn-save admin-create-btn"
        :disabled="!adminNewName || adminCreating || (adminNewKind === 'project_token' && !adminNewProjectId)"
        @click="adminCreate">
        {{ adminCreating ? t('Saving…') : t('Create') }}
      </button>
      <button class="btn-cancel" @click="adminCreateOpen = false">{{ t('Cancel') }}</button>
    </div>

    <!-- New token banner -->
    <div v-if="adminCreatedToken" class="admin-new-token-banner">
      <span class="admin-new-token-label">{{ t('Token value (save this — shown only once):') }}</span>
      <code class="admin-new-token-value copyable" @click="copy(adminCreatedToken)" :title="t('Click to copy')">{{ adminCreatedToken }}</code>
      <span class="copy-hint" v-if="copied === adminCreatedToken">{{ t('Copied') }}</span>
      <button class="btn-cancel admin-dismiss" @click="adminCreatedToken = ''">{{ t('Close') }}</button>
    </div>

    <!-- Token list -->
    <div class="tp-content">
      <div v-if="adminLoading" class="admin-empty">{{ t('Loading…') }}</div>
      <div v-else-if="!adminTokens.length" class="admin-empty">{{ t('No tokens yet.') }}</div>
      <table v-else class="admin-table">
        <thead>
          <tr>
            <th>{{ t('Kind') }}</th>
            <th>{{ t('Name') }}</th>
            <th>{{ t('Project') }}</th>
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
            <td class="admin-project-cell">{{ tok.kind === 'project_token' ? projectName(tok.project_id) : '—' }}</td>
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

    <!-- Token action confirm -->
    <Teleport to="body">
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
    </Teleport>
  </div>
</template>

<style scoped>
.tp-app {
  width: 100%; max-width: 1600px; margin: 0 auto;
  padding: 6px 16px 12px;
  display: flex; flex-direction: column;
  gap: 6px; height: 100vh; box-sizing: border-box;
}
.toolbar {
  display: flex; align-items: center; gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--surface-panel);
  backdrop-filter: blur(12px);
}
[data-theme="dark"] .toolbar {
  border-color: rgba(0,212,138,0.12);
  box-shadow: inset 0 1px 0 rgba(0,212,138,0.04);
}
.tp-title { font-size: 12px; font-weight: 600; color: var(--text-primary); }
.toolbar-spacer { flex: 1; }
.admin-create-form {
  display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  padding: 10px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--surface-panel);
}
.tp-content {
  flex: 1; overflow: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--surface);
}
.admin-project-cell { font-size: 11px; color: var(--text-secondary); max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* Column widths for 7-col layout (Kind / Name / Project / Status / Created / Last used / Actions) */
:deep(.admin-table th:nth-child(1)), :deep(.admin-table td:nth-child(1)) { width: 140px; }
:deep(.admin-table th:nth-child(2)), :deep(.admin-table td:nth-child(2)) { width: 200px; }
:deep(.admin-table th:nth-child(3)), :deep(.admin-table td:nth-child(3)) { width: auto; }
:deep(.admin-table th:nth-child(4)), :deep(.admin-table td:nth-child(4)) { width: 140px; white-space: nowrap; }
:deep(.admin-table th:nth-child(5)), :deep(.admin-table td:nth-child(5)) { width: 80px; }
:deep(.admin-table th:nth-child(6)), :deep(.admin-table td:nth-child(6)) { width: 90px; }
:deep(.admin-table th:nth-child(7)), :deep(.admin-table td:nth-child(7)) { width: 180px; white-space: nowrap; }
</style>
