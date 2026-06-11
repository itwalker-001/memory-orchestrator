<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import {
  NCard, NSelect, NInput, NButton, NDataTable, NTag, NSwitch, NSpace,
  NText, NForm, NFormItem, NEmpty, NIcon, useMessage,
} from 'naive-ui'
import AppHeader from './AppHeader.vue'
import BaseModal from './BaseModal.vue'
import { apiFetch, apiJSON, errText, copyText } from './api.js'
import { useAppStore } from './stores/app.js'
import { IconLock, IconPlus, IconSync, IconTrash, IconClone, IconCheck } from './icons.js'

const router = useRouter()
const appStore = useAppStore()
const { isDark, lang } = storeToRefs(appStore)
const { t } = appStore
const message = useMessage()

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
  await copyText(text)
  copied.value = text
  setTimeout(() => { copied.value = null }, 1500)
}

// Reveal (decrypt) a stored token and copy it to the clipboard. Tracks the row id
// so the action button can flash a check mark on success.
const copiedRowId = ref(null)
const revealingId = ref(null)
async function copyToken(tok) {
  revealingId.value = tok.id
  try {
    const data = await apiJSON(`/tokens/${tok.id}/reveal`, { method: 'POST', skipErrorToast: true })
    await copyText(data.token)
    copiedRowId.value = tok.id
    setTimeout(() => { if (copiedRowId.value === tok.id) copiedRowId.value = null }, 1500)
  } catch (e) {
    // The backend's 409 detail is hardcoded English; localize it here instead
    // of passing the raw detail through to the toast.
    const status = e?.response?.status
    message.error(status === 409 || status === 404
      ? t('Token cannot be revealed (created before encryption was enabled, or key unavailable)')
      : (errText(e) || t('Token cannot be revealed (created before encryption was enabled, or key unavailable)')))
  } finally {
    revealingId.value = null
  }
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

const kindOptions = [
  { label: 'ui_admin', value: 'ui_admin' },
  { label: 'project_token', value: 'project_token' },
]
const projectOptions = computed(() => projects.value.map(p => ({ label: p.display_name || p.slug, value: p.id })))

// Display order: by token kind priority, then newest first within each kind.
const KIND_ORDER = { ui_admin: 0, project_token: 1, mcp_client: 2 }
const sortedTokens = computed(() =>
  [...adminTokens.value].sort((a, b) => {
    const ka = KIND_ORDER[a.kind] ?? 99
    const kb = KIND_ORDER[b.kind] ?? 99
    if (ka !== kb) return ka - kb
    return (b.created_at || '').localeCompare(a.created_at || '')
  })
)

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
      apiFetch(`/tokens`),
      apiFetch(`/projects`),
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
    const data = await apiJSON(`/tokens`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
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
  await apiJSON(`/tokens/${tok.id}`, {
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
      const data = await apiJSON(`/tokens/${tok.id}/reset`, { method: 'POST' })
      adminCreatedToken.value = data.token
      await load()
    } else {
      await apiJSON(`/tokens/${tok.id}`, { method: 'DELETE' })
      await load()
    }
  } finally {
    isTokenActioning.value = false
    tokenActionTarget.value = null
  }
}

async function logout() {
  await fetch(`/api/logout`, { method: 'POST' })
  router.push('/memories')
}

const columns = computed(() => [
  {
    title: t('Kind'),
    key: 'kind',
    width: 140,
    render: row => h(NTag, { size: 'small', type: row.kind === 'ui_admin' ? 'info' : 'success', bordered: false }, { default: () => row.kind }),
  },
  {
    title: t('Project'),
    key: 'project',
    width: 160,
    ellipsis: { tooltip: true },
    render: row => row.kind === 'project_token' ? projectName(row.project_id) : '—',
  },
  { title: t('Name'), key: 'name', ellipsis: { tooltip: true } },
  {
    title: t('Status'),
    key: 'status',
    width: 150,
    render: row => h(NSpace, { align: 'center', size: 8, wrap: false }, () => [
      h(NSwitch, { value: row.enabled, size: 'small', 'onUpdate:value': () => adminToggle(row) }),
      h(NText, { depth: 3, style: 'font-size:11px' }, () => row.enabled ? t('Enabled') : t('Disabled')),
    ]),
  },
  { title: t('Created'), key: 'created_at', width: 90, render: row => relTime(row.created_at) },
  { title: t('Last used'), key: 'last_used_at', width: 90, render: row => row.last_used_at ? relTime(row.last_used_at) : '—' },
  {
    title: '',
    key: 'actions',
    width: 240,
    render: row => h('div', { class: 'tp-actions' }, [
      h(NSpace, { size: 6, wrap: false, justify: 'end' }, () => [
      row.revealable
        ? h(NButton, {
            size: 'tiny',
            type: copiedRowId.value === row.id ? 'success' : 'default',
            loading: revealingId.value === row.id,
            title: t('Copy token'),
            onClick: () => copyToken(row),
          }, {
            icon: () => h(NIcon, null, { default: () => h(copiedRowId.value === row.id ? IconCheck : IconClone) }),
            default: () => copiedRowId.value === row.id ? t('Copied') : t('Copy'),
          })
        : null,
      h(NButton, { size: 'tiny', onClick: () => openTokenAction(row, 'reset') }, { icon: () => h(NIcon, null, { default: () => h(IconSync) }), default: () => t('Reset') }),
      h(NButton, { size: 'tiny', type: 'error', onClick: () => openTokenAction(row, 'revoke') }, { icon: () => h(NIcon, null, { default: () => h(IconTrash) }), default: () => t('Revoke') }),
      ]),
    ]),
  },
])

onMounted(() => { load() })
</script>

<template>
  <div class="tp-app">
    <AppHeader :loginOpen="false"
      @logout="logout" />

    <!-- Toolbar -->
    <n-card size="small" :bordered="true">
      <n-space align="center" justify="space-between">
        <n-space align="center" :size="8">
          <n-icon :size="16"><IconLock /></n-icon>
          <n-text strong>{{ t('API Tokens') }}</n-text>
        </n-space>
        <n-button size="small" type="primary" @click="adminCreateOpen = !adminCreateOpen">
          <template #icon><n-icon><IconPlus /></n-icon></template>
          {{ t('New') }}
        </n-button>
      </n-space>
    </n-card>

    <!-- Create form -->
    <n-card v-if="adminCreateOpen" size="small" :bordered="true">
      <n-space align="center" :size="10">
        <n-select v-model:value="adminNewKind" :options="kindOptions" size="small" style="width:160px" />
        <n-select v-if="adminNewKind === 'project_token'" v-model:value="adminNewProjectId" :options="projectOptions" size="small" style="width:200px" :placeholder="t('Select project…')" />
        <n-input v-model:value="adminNewName" size="small" style="width:220px" :placeholder="t('Name…')" @keydown.enter="adminCreate" />
        <n-button size="small" type="primary"
          :disabled="!adminNewName || (adminNewKind === 'project_token' && !adminNewProjectId)"
          :loading="adminCreating" @click="adminCreate">
          {{ t('Create') }}
        </n-button>
        <n-button size="small" @click="adminCreateOpen = false">{{ t('Cancel') }}</n-button>
      </n-space>
    </n-card>

    <!-- New token banner -->
    <n-card v-if="adminCreatedToken" size="small" :bordered="true">
      <n-space align="center" :size="10">
        <n-text depth="3" style="font-size:11px">{{ t('Token value (save this — shown only once):') }}</n-text>
        <n-text code style="cursor:pointer;word-break:break-all" @click="copy(adminCreatedToken)" :title="t('Click to copy')">{{ adminCreatedToken }}</n-text>
        <n-text v-if="copied === adminCreatedToken" type="success" style="font-size:11px">{{ t('Copied') }}</n-text>
        <n-button size="tiny" style="margin-left:auto" @click="adminCreatedToken = ''">{{ t('Close') }}</n-button>
      </n-space>
    </n-card>

    <!-- Token list -->
    <div class="tp-content">
      <n-data-table
        flex-height
        size="small"
        :columns="columns"
        :data="sortedTokens"
        :row-key="row => row.id"
        :loading="adminLoading"
        style="height:100%"
      />
    </div>

    <!-- Token action confirm -->
    <BaseModal :show="!!tokenActionTarget" :mask-closable="true" @close="tokenActionTarget = null">
      <n-card v-if="tokenActionTarget" :title="tokenActionTarget.action === 'reset' ? t('Reset token') : t('Revoke token')" closable style="width:420px" :bordered="false" @close="tokenActionTarget = null">
        <n-text strong style="display:block">{{ tokenActionTarget.tok.name }}</n-text>
        <n-text depth="3" tag="p" style="margin-top:8px;font-size:12px">
          {{ tokenActionTarget.action === 'reset' ? t('Reset token desc') : t('Revoke token desc') }}
        </n-text>
        <template #footer>
          <n-space justify="end">
            <n-button @click="tokenActionTarget = null">{{ t('Cancel') }}</n-button>
            <n-button :type="tokenActionTarget.action === 'reset' ? 'primary' : 'error'" :loading="isTokenActioning" @click="confirmTokenAction">
              {{ tokenActionTarget.action === 'reset' ? t('Reset') : t('Revoke') }}
            </n-button>
          </n-space>
        </template>
      </n-card>
    </BaseModal>
  </div>
</template>

<style scoped>
.tp-app {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 8px 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  height: 100vh;
  box-sizing: border-box;
}
.tp-content {
  flex: 1;
  min-height: 0;
}
.tp-content :deep(.tp-actions) {
  opacity: 0;
  transition: opacity 0.12s ease;
}
.tp-content :deep(.n-data-table-tr:hover .tp-actions) {
  opacity: 1;
}
</style>
