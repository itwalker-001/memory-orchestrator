<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard, NSelect, NButton, NIcon, NText, NTag, NSpace, NEmpty, NInput,
  NAlert, NSpin, useMessage,
} from 'naive-ui'
import AppHeader from './AppHeader.vue'
import { apiFetch, apiJSON, errText, copyText } from './api.js'
import { useAppStore } from './stores/app.js'
import { IconInfo, IconClone, IconCheck, IconLock, IconDownload } from './icons.js'

const router = useRouter()
const app = useAppStore()
const { t } = app
const message = useMessage()

function goTokens() { router.push('/tokens') }

async function logout() {
  await fetch(`/api/logout`, { method: 'POST' })
  router.push('/memories')
}

// ── Server base URL: defaults to the origin the user is viewing the UI from. In
// Vite dev the page runs on :5173, so derive a sensible default from the current
// hostname on the standard server port. Editable — the user can override it.
function defaultBaseUrl() {
  const { origin, protocol, hostname, port } = window.location
  if (port === '5173') return `${protocol}//${hostname}:8765`
  return origin
}
const baseUrl = ref(defaultBaseUrl())

// ── Projects + selection (shares the strip's localStorage key) ──────────────────
const LS_PROJECT_KEY = 'mo_selected_project'
const projects = ref([])
const selectedSlug = ref('')
const loading = ref(true)

const projectOptions = computed(() =>
  projects.value.map(p => ({ label: p.display_name || p.slug, value: p.slug })))

const selectedProject = computed(() =>
  projects.value.find(p => p.slug === selectedSlug.value) || null)

// ── Tokens for the selected project ─────────────────────────────────────────────
const allTokens = ref([])
const projectTokens = computed(() => {
  const p = selectedProject.value
  if (!p) return []
  return allTokens.value.filter(tk => tk.kind === 'project_token' && tk.project_id === p.id)
})

// Revealed plaintext keyed by token id (filled on demand via /reveal).
const revealed = ref({})
const revealingId = ref(null)

// The token to embed in the commands: prefer an already-revealed enabled token,
// else leave the placeholder so the snippet stays copy-paste-able.
const activeToken = computed(() => {
  const enabled = projectTokens.value.filter(tk => tk.enabled)
  for (const tk of enabled) {
    if (revealed.value[tk.id]) return revealed.value[tk.id]
  }
  return '<your-project-token>'
})

async function revealToken(tk) {
  revealingId.value = tk.id
  try {
    const data = await apiJSON(`/tokens/${tk.id}/reveal`, { method: 'POST', skipErrorToast: true })
    revealed.value = { ...revealed.value, [tk.id]: data.token }
  } catch (e) {
    const status = e?.response?.status
    message.error(status === 409 || status === 404
      ? t('Token cannot be revealed (created before encryption was enabled, or key unavailable)')
      : (errText(e) || t('Token cannot be revealed (created before encryption was enabled, or key unavailable)')))
  } finally {
    revealingId.value = null
  }
}

function maskToken(tk) {
  if (revealed.value[tk.id]) return revealed.value[tk.id]
  return '••••••••••••••••••••••••'
}

// ── Downloadable artifacts (mo-mcp wheels served by the server) ─────────────────
const downloads = ref([])
const selectedWheelName = ref('')

function fmtSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}

function downloadUrl(name) {
  return `${baseUrl.value}/api/downloads/${encodeURIComponent(name)}`
}

function parseWheelVersion(name) {
  const match = name.match(/^memory_orchestrator_mcp-(.+)-py3-none-any\.whl$/)
  if (!match) return []
  return match[1].split(/[.-]/).map(part => {
    const n = Number.parseInt(part, 10)
    return Number.isNaN(n) ? part : n
  })
}

function compareWheelNames(a, b) {
  const av = parseWheelVersion(a)
  const bv = parseWheelVersion(b)
  const len = Math.max(av.length, bv.length)
  for (let i = 0; i < len; i += 1) {
    const ai = av[i]
    const bi = bv[i]
    if (ai === undefined) return -1
    if (bi === undefined) return 1
    if (typeof ai === 'number' && typeof bi === 'number') {
      if (ai !== bi) return ai - bi
      continue
    }
    const as = String(ai)
    const bs = String(bi)
    if (as !== bs) return as.localeCompare(bs)
  }
  return a.localeCompare(b)
}

const wheelDownloads = computed(() =>
  downloads.value
    .filter(f => f.name.endsWith('.whl'))
    .slice()
    .sort((a, b) => compareWheelNames(b.name, a.name)))

// ── Command snippets ────────────────────────────────────────────────────────────
const wheelName = computed(() => {
  const selected = wheelDownloads.value.find(f => f.name === selectedWheelName.value)
  if (selected) return selected.name
  const latest = wheelDownloads.value[0]
  if (latest) return latest.name
  return `memory_orchestrator_mcp-${app.version || '<version>'}-py3-none-any.whl`
})

const cmdInstall = computed(() =>
  `uv tool install --force ${wheelName.value}`)

function selectWheel(name) {
  selectedWheelName.value = name
}

watch(wheelDownloads, (items) => {
  if (!items.length) {
    selectedWheelName.value = ''
    return
  }
  if (!items.some(item => item.name === selectedWheelName.value)) {
    selectedWheelName.value = items[0].name
  }
}, { immediate: true })

// Display form is multi-line for readability; the copied form is single-line so it
// runs as-is in any shell. Bash backslash continuations break in Win cmd/PowerShell.
const cmdSetup = computed(() =>
  `mo-mcp setup \\\n  --client claude \\\n  --base-url ${baseUrl.value} \\\n  --project-token ${activeToken.value}`)
const cmdSetupCopy = computed(() =>
  `mo-mcp setup --client claude --base-url ${baseUrl.value} --project-token ${activeToken.value}`)

const cmdSetupCodex = computed(() =>
  `mo-mcp setup \\\n  --client codex \\\n  --base-url ${baseUrl.value} \\\n  --project-token ${activeToken.value}`)
const cmdSetupCodexCopy = computed(() =>
  `mo-mcp setup --client codex --base-url ${baseUrl.value} --project-token ${activeToken.value}`)

const cmdDoctor = computed(() =>
  `mo-mcp doctor --base-url ${baseUrl.value}`)

const cmdUninstallProject = `mo-mcp teardown --client claude`
const cmdUninstallCli = `uv tool uninstall memory-orchestrator-mcp`

// ── Copy helper (per snippet, flashes a check) ──────────────────────────────────
const copiedKey = ref(null)
async function copySnippet(key, text) {
  try {
    await copyText(text)
    copiedKey.value = key
    setTimeout(() => { if (copiedKey.value === key) copiedKey.value = null }, 1500)
  } catch {
    message.error(t('Copy failed'))
  }
}

// ── Load ────────────────────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  try {
    const [projR, tokR, dlR] = await Promise.all([
      apiFetch('/projects'), apiFetch('/tokens'), apiFetch('/downloads'),
    ])
    if (projR.status === 401) { router.push('/memories'); return }
    projects.value = projR.ok ? await projR.json() : []
    allTokens.value = tokR.ok ? await tokR.json() : []
    downloads.value = dlR.ok ? await dlR.json() : []
    const saved = localStorage.getItem(LS_PROJECT_KEY)
    const match = saved && projects.value.find(p => p.slug === saved)
    selectedSlug.value = (match || projects.value[0])?.slug || ''
  } finally {
    loading.value = false
  }
}

function onSelectProject(slug) {
  selectedSlug.value = slug
  localStorage.setItem(LS_PROJECT_KEY, slug)
}

onMounted(() => { load() })
</script>

<template>
  <div class="hp-app">
    <AppHeader :loginOpen="false" @logout="logout" />

    <div class="hp-page-body">
      <n-card class="hp-modal-card" :bordered="true" size="small">
        <template #header>
          <n-space align="center" :size="8">
            <n-icon :size="18"><IconInfo /></n-icon>
            <span>{{ t('MCP Setup Guide') }}</span>
          </n-space>
        </template>

      <n-spin :show="loading">
        <div class="hp-content">
          <n-text depth="3" tag="div" style="font-size:12px;margin-bottom:4px">
            {{ t('Connect a project to this Memory Orchestrator server via the mo-mcp client.') }}
          </n-text>

        <!-- Project + server selector -->
        <n-card size="small" :bordered="true">
          <n-space align="center" :size="16" wrap>
            <n-space align="center" :size="8">
              <n-text depth="3" style="font-size:12px">{{ t('Project') }}</n-text>
              <n-select
                :value="selectedSlug"
                :options="projectOptions"
                size="small"
                style="width:240px"
                :placeholder="t('Select project…')"
                @update:value="onSelectProject"
              />
            </n-space>
            <n-space align="center" :size="8">
              <n-text depth="3" style="font-size:12px">{{ t('Server URL') }}</n-text>
              <n-input
                v-model:value="baseUrl"
                size="small"
                style="width:260px"
                :placeholder="t('Server URL')"
              />
            </n-space>
          </n-space>
        </n-card>

        <n-empty v-if="!selectedProject && !loading" :description="t('Select or create project')" style="padding:40px 0" />

        <template v-else-if="selectedProject">
          <!-- Token picker -->
          <n-card size="small" :bordered="true" :title="t('Project Token')">
            <template #header-extra>
              <n-button size="tiny" text @click="goTokens">
                <template #icon><n-icon><IconLock /></n-icon></template>
                {{ t('Manage tokens') }}
              </n-button>
            </template>

            <n-empty v-if="projectTokens.length === 0"
              :description="t('No project token for this project yet — create one in Tokens.')"
              style="padding:20px 0">
              <template #extra>
                <n-button size="small" @click="goTokens">{{ t('Go to Tokens') }}</n-button>
              </template>
            </n-empty>

            <div v-else class="hp-token-list">
              <div v-for="tk in projectTokens" :key="tk.id" class="hp-token-row">
                <n-tag size="small" :type="tk.enabled ? 'success' : 'default'" :bordered="false">
                  {{ tk.enabled ? t('Enabled') : t('Disabled') }}
                </n-tag>
                <n-text strong style="font-size:13px">{{ tk.name }}</n-text>
                <n-text code class="hp-token-value">{{ maskToken(tk) }}</n-text>
                <div class="hp-token-spacer" />
                <n-button
                  v-if="tk.revealable && !revealed[tk.id]"
                  size="tiny"
                  :loading="revealingId === tk.id"
                  @click="revealToken(tk)"
                >
                  {{ t('Show & use') }}
                </n-button>
                <n-tag v-else-if="revealed[tk.id]" size="tiny" type="success" :bordered="false">
                  <template #icon><n-icon><IconCheck /></n-icon></template>
                  {{ t('In use below') }}
                </n-tag>
                <n-text v-else depth="3" style="font-size:11px">
                  {{ t('Cannot reveal — reset it in Tokens') }}
                </n-text>
              </div>
            </div>

            <n-alert v-if="activeToken === '<your-project-token>' && projectTokens.length"
              type="info" :show-icon="false" style="margin-top:12px;font-size:12px">
              {{ t('Click “Show & use” above to embed the real token into the commands below.') }}
            </n-alert>
          </n-card>

          <!-- Step 1: install CLI -->
          <n-card size="small" :bordered="true" :title="t('1. Install / upgrade the CLI')">
            <n-text depth="3" tag="p" class="hp-step-desc">
              {{ t('Install the mo-mcp wheel as a global command. --force overwrites an older version.') }}
            </n-text>

            <!-- Downloadable artifacts -->
            <div v-if="wheelDownloads.length" class="hp-dl-list">
              <div
                v-for="f in wheelDownloads"
                :key="f.name"
                class="hp-dl-row"
                :class="{ 'is-selected': f.name === wheelName }"
                role="button"
                tabindex="0"
                @click="selectWheel(f.name)"
                @keydown.enter.prevent="selectWheel(f.name)"
                @keydown.space.prevent="selectWheel(f.name)"
              >
                <n-icon :size="16" class="hp-dl-icon"><IconDownload /></n-icon>
                <n-text code class="hp-dl-name">{{ f.name }}</n-text>
                <n-text depth="3" style="font-size:11px">{{ fmtSize(f.size) }}</n-text>
                <div class="hp-dl-spacer" />
                <n-tag v-if="f.name === wheelName" size="small" type="success" :bordered="false">
                  {{ t('selected') }}
                </n-tag>
                <n-button size="tiny" tag="a" :href="downloadUrl(f.name)" :download="f.name" @click.stop>
                  <template #icon><n-icon><IconDownload /></n-icon></template>
                  {{ t('Download') }}
                </n-button>
              </div>
            </div>
            <n-text v-else depth="3" tag="p" class="hp-hint">
              {{ t('No downloadable wheel on the server — build one and place it in the downloads directory.') }}
            </n-text>

            <div class="hp-code">
              <pre>{{ cmdInstall }}</pre>
              <n-button class="hp-copy" size="tiny" :type="copiedKey === 'install' ? 'success' : 'default'"
                @click="copySnippet('install', cmdInstall)">
                <template #icon><n-icon><IconCheck v-if="copiedKey === 'install'" /><IconClone v-else /></n-icon></template>
                {{ copiedKey === 'install' ? t('Copied') : t('Copy') }}
              </n-button>
            </div>
            <n-text depth="3" tag="p" class="hp-hint">
              {{ t('Run this in the directory holding the downloaded .whl file. Click a wheel above to match the command.') }}
            </n-text>
          </n-card>

          <!-- Step 2: wire the project -->
          <n-card size="small" :bordered="true" :title="t('2. Wire up the project')">
            <n-text depth="3" tag="p" class="hp-step-desc">
              {{ t('Run from the project root — config is written into the current directory.') }}
            </n-text>
            <div class="hp-code">
              <pre>cd &lt;path-to-your-project&gt;

{{ cmdSetup }}</pre>
              <n-button class="hp-copy" size="tiny" :type="copiedKey === 'setup' ? 'success' : 'default'"
                @click="copySnippet('setup', cmdSetupCopy)">
                <template #icon><n-icon><IconCheck v-if="copiedKey === 'setup'" /><IconClone v-else /></n-icon></template>
                {{ copiedKey === 'setup' ? t('Copied') : t('Copy') }}
              </n-button>
            </div>
            <n-text depth="3" tag="p" class="hp-hint">{{ t('For Codex, use --client codex:') }}</n-text>
            <div class="hp-code">
              <pre>{{ cmdSetupCodex }}</pre>
              <n-button class="hp-copy" size="tiny" :type="copiedKey === 'setup-codex' ? 'success' : 'default'"
                @click="copySnippet('setup-codex', cmdSetupCodexCopy)">
                <template #icon><n-icon><IconCheck v-if="copiedKey === 'setup-codex'" /><IconClone v-else /></n-icon></template>
                {{ copiedKey === 'setup-codex' ? t('Copied') : t('Copy') }}
              </n-button>
            </div>
          </n-card>

          <!-- Step 3: verify -->
          <n-card size="small" :bordered="true" :title="t('3. Verify the connection')">
            <div class="hp-code">
              <pre>cd &lt;path-to-your-project&gt;
{{ cmdDoctor }}</pre>
              <n-button class="hp-copy" size="tiny" :type="copiedKey === 'doctor' ? 'success' : 'default'"
                @click="copySnippet('doctor', cmdDoctor)">
                <template #icon><n-icon><IconCheck v-if="copiedKey === 'doctor'" /><IconClone v-else /></n-icon></template>
                {{ copiedKey === 'doctor' ? t('Copied') : t('Copy') }}
              </n-button>
            </div>
            <n-text depth="3" tag="p" class="hp-hint">
              {{ t('doctor checks client wiring, server reachability, and token validity.') }}
            </n-text>
          </n-card>

          <!-- Security note -->
          <n-alert type="warning" :title="t('Security')" :show-icon="true" style="font-size:12px">
            {{ t('.mcp.json contains the project token — add it to .gitignore so it is never committed.') }}
          </n-alert>

          <!-- Uninstall -->
          <n-card size="small" :bordered="true" :title="t('Uninstall')">
            <n-text depth="3" tag="p" class="hp-step-desc">{{ t('Remove MCP wiring from a project (keeps the CLI):') }}</n-text>
            <div class="hp-code">
              <pre>cd &lt;path-to-your-project&gt;
{{ cmdUninstallProject }}</pre>
              <n-button class="hp-copy" size="tiny" :type="copiedKey === 'uninstall-p' ? 'success' : 'default'"
                @click="copySnippet('uninstall-p', cmdUninstallProject)">
                <template #icon><n-icon><IconCheck v-if="copiedKey === 'uninstall-p'" /><IconClone v-else /></n-icon></template>
                {{ copiedKey === 'uninstall-p' ? t('Copied') : t('Copy') }}
              </n-button>
            </div>
            <n-text depth="3" tag="p" class="hp-hint">{{ t('Remove the CLI tool entirely:') }}</n-text>
            <div class="hp-code">
              <pre>{{ cmdUninstallCli }}</pre>
              <n-button class="hp-copy" size="tiny" :type="copiedKey === 'uninstall-c' ? 'success' : 'default'"
                @click="copySnippet('uninstall-c', cmdUninstallCli)">
                <template #icon><n-icon><IconCheck v-if="copiedKey === 'uninstall-c'" /><IconClone v-else /></n-icon></template>
                {{ copiedKey === 'uninstall-c' ? t('Copied') : t('Copy') }}
              </n-button>
            </div>
          </n-card>
        </template>
        </div>
      </n-spin>
      </n-card>
    </div>
  </div>
</template>

<style scoped>
.hp-app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.hp-page-body {
  flex: 1;
  width: 100%;
  max-width: 960px;
  margin: 0 auto;
  padding: 8px 16px 24px;
}
.hp-modal-card {
  width: 100%;
}
.hp-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 4px 0 8px;
}
.hp-title-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 8px 4px 0;
}
.hp-title-icon { color: var(--n-primary-color, #63e2b7); margin-top: 2px; }
.hp-step-desc { margin: 0 0 10px; font-size: 12px; line-height: 1.5; }
.hp-hint { margin: 10px 0 0; font-size: 11px; line-height: 1.5; }

/* Token rows */
.hp-token-list { display: flex; flex-direction: column; gap: 8px; }
.hp-token-row { display: flex; align-items: center; gap: 10px; }
.hp-token-value { font-size: 12px; word-break: break-all; opacity: 0.85; }
.hp-token-spacer { flex: 1; }

/* Download list */
.hp-dl-list { display: flex; flex-direction: column; gap: 6px; margin: 0 0 12px; }
.hp-dl-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  border: 1px solid var(--n-border-color, rgba(0,0,0,0.08));
  border-radius: 6px;
  background: transparent;
  cursor: pointer;
  outline: none;
}
.hp-dl-row:hover {
  background: var(--n-action-color, #f6f8fa);
}
.hp-dl-row:focus-visible {
  box-shadow: 0 0 0 2px var(--n-primary-color-suppl, rgba(24,160,88,0.18));
}
.hp-dl-row.is-selected {
  border-color: var(--n-primary-color, #63e2b7);
  background: var(--n-action-color, #f6f8fa);
}
.hp-dl-icon { color: var(--n-primary-color, #63e2b7); }
.hp-dl-name { font-size: 12px; word-break: break-all; }
.hp-dl-spacer { flex: 1; }

/* Code block with a copy button anchored top-right */
.hp-code {
  position: relative;
  background: var(--n-action-color, #f6f8fa);
  border: 1px solid var(--n-border-color, rgba(0,0,0,0.08));
  border-radius: 6px;
  padding: 12px 14px;
}
.hp-code pre {
  margin: 0;
  font-family: 'JetBrains Mono', 'Fira Code', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  padding-right: 64px;
}
.hp-copy {
  position: absolute;
  top: 8px;
  right: 8px;
}
</style>
