<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppHeader from './AppHeader.vue'
import { BASE, apiFetch } from './api.js'
import { useAppStore } from './stores/app.js'
import IconChevron from './icons/IconChevron.svg'
import IconCheck from './icons/IconCheck.svg'
import IconFetchRefresh from './icons/IconFetchRefresh.svg'
import IconDownload from './icons/IconDownload.svg'
import IconUpload from './icons/IconUpload.svg'
import IconClose from './icons/IconClose.svg'
import IconWarn from './icons/IconWarn.svg'
import IconCheckLg from './icons/IconCheckLg.svg'

const router = useRouter()
const appStore = useAppStore()
const { isDark, lang } = storeToRefs(appStore)
const { t, toggleTheme, toggleLang } = appStore

// ── Settings form ──
const KEY_SENTINEL = '__keep__'
const settingsTab = ref('settings')
const isSaving = ref(false)
const saveHint = ref('')
const form = ref({
  extraction_base_url: '', extraction_model: '', extraction_api_key: '',
  hook_cooldown_sec: '', hook_min_turns: '', hook_budget_tokens: '',
  search_top_k: '', dup_threshold: '',
  rerank_enabled: 'false', score_rerank_blend: '',
  score_cosine_weight: '', score_importance_weight: '', score_recency_weight: '',
  score_recency_half_life: '',
  score_type_feedback: '', score_type_project: '', score_type_user: '', score_type_reference: '',
})

// ── Model combobox ──
const availableModels = ref([])
const isFetchingModels = ref(false)
const modelDropOpen = ref(false)
const modelHighlight = ref(-1)
const modelFilteredList = computed(() => {
  if (!availableModels.value.length) return []
  const q = (form.value.extraction_model || '').toLowerCase()
  return q ? availableModels.value.filter(m => m.toLowerCase().includes(q)) : availableModels.value
})
function onModelFocus() { if (availableModels.value.length) modelDropOpen.value = true; modelHighlight.value = -1 }
function onModelBlur() { setTimeout(() => { modelDropOpen.value = false; modelHighlight.value = -1 }, 150) }
function onModelKeydown(e) {
  if (!modelDropOpen.value) { if (e.key === 'ArrowDown' || e.key === 'Enter') { modelDropOpen.value = true; e.preventDefault() }; return }
  const list = modelFilteredList.value
  if (e.key === 'ArrowDown') { modelHighlight.value = Math.min(modelHighlight.value + 1, list.length - 1); e.preventDefault() }
  else if (e.key === 'ArrowUp') { modelHighlight.value = Math.max(modelHighlight.value - 1, -1); e.preventDefault() }
  else if (e.key === 'Enter') { if (modelHighlight.value >= 0 && list[modelHighlight.value]) selectModel(list[modelHighlight.value]); e.preventDefault() }
  else if (e.key === 'Escape') { modelDropOpen.value = false; modelHighlight.value = -1 }
}
function selectModel(m) { form.value.extraction_model = m; modelDropOpen.value = false; modelHighlight.value = -1 }
async function fetchModels() {
  if (!form.value.extraction_base_url) return
  isFetchingModels.value = true
  try {
    const params = new URLSearchParams({ base_url: form.value.extraction_base_url })
    const key = form.value.extraction_api_key
    const headers = (key && key !== '***' && key !== KEY_SENTINEL) ? { 'X-Api-Key': key } : {}
    const models = await apiFetch(`${BASE}/models?${params}`, { headers }).then(r => r.ok ? r.json() : [])
    availableModels.value = models
    if (models.length) modelDropOpen.value = true
  } finally { isFetchingModels.value = false }
}

// ── Scoring helpers ──
function wf(key, def) { return Math.max(0, parseFloat(form.value[key]) || def) }
const weightSum = computed(() => {
  const s = wf('score_cosine_weight', 0.6) + wf('score_importance_weight', 0.3) + wf('score_recency_weight', 0.1)
  return (Math.round(s * 100) / 100).toFixed(2)
})
const weightSumOk = computed(() => Math.abs(parseFloat(weightSum.value) - 1.0) < 0.015)
function decayPct(days) { return Math.round(Math.exp(-days / (parseFloat(form.value.score_recency_half_life) || 60)) * 100) }
function typeBarPct(val) { return Math.round(Math.min(3, Math.max(0, parseFloat(val) || 1)) / 3 * 100) + '%' }
const blendFmt = computed(() => (parseFloat(form.value.score_rerank_blend) || 0.8).toFixed(2))
const counterBlendFmt = computed(() => (1 - (parseFloat(form.value.score_rerank_blend) || 0.8)).toFixed(2))

// ── API ──
async function load() {
  try {
    const r = await apiFetch(`${BASE}/settings`)
    if (r.status === 401) { router.push('/memories'); return }
    const data = await r.json()
    form.value = { ...form.value, ...data, extraction_api_key: data.extraction_api_key === '***' ? KEY_SENTINEL : (data.extraction_api_key || '') }
    availableModels.value = []; modelDropOpen.value = false; modelHighlight.value = -1
    saveHint.value = ''
  } catch {}
}

async function saveSettings() {
  isSaving.value = true; saveHint.value = ''
  try {
    const payload = Object.fromEntries(Object.entries(form.value).filter(([k, v]) => {
      if (k === 'extraction_api_key') return v !== KEY_SENTINEL && v !== ''
      return v !== ''
    }))
    const r = await apiFetch(`${BASE}/settings`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (!r.ok) { const err = await r.json().catch(() => ({})); saveHint.value = `Error ${r.status}: ${err.detail || r.statusText}`; return }
    saveHint.value = t('Saved')
    setTimeout(() => { saveHint.value = '' }, 2000)
  } catch (e) { saveHint.value = `Error: ${e.message}` }
  finally { isSaving.value = false }
}

async function exportMemories() {
  const r = await apiFetch(`${BASE}/backup`)
  if (!r.ok) { alert('Backup failed: ' + (await r.text())); return }
  const blob = await r.blob()
  const cd = r.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : `mo-backup-${new Date().toISOString().slice(0, 10)}.sql`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = filename
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

// ── Import ──
const importFileRef = ref(null)
const importModalOpen = ref(false)
const importPreview = ref(null)
const importProgress = ref({ done: 0, total: 0, running: false, errorMsg: '' })

function openImport() { importFileRef.value?.click() }
function onImportFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  importPreview.value = { file, name: file.name }
  importProgress.value = { done: 0, total: 0, running: false, errorMsg: '' }
  importModalOpen.value = true
}
async function confirmImport() {
  if (!importPreview.value?.file) return
  importProgress.value.running = true
  try {
    const fd = new FormData()
    fd.append('file', importPreview.value.file)
    const r = await apiFetch(`${BASE}/restore`, { method: 'POST', body: fd })
    if (!r.ok) {
      const text = await r.text()
      importProgress.value = { done: 0, total: -1, running: false, errorMsg: text.slice(0, 400) }
      return
    }
    importProgress.value = { done: 1, total: 1, running: false, errorMsg: '' }
  } catch (err) {
    importProgress.value = { done: 0, total: -1, running: false, errorMsg: String(err) }
  }
}

async function logout() {
  await fetch(`${BASE}/logout`, { method: 'POST' })
  router.push('/memories')
}

onMounted(() => { load() })
</script>

<template>
  <div class="sp-app">
    <AppHeader :loginOpen="false"
      @open-settings="() => {}" @logout="logout">
      <template #nav>
        <router-link to="/memories">← {{ t('Memories') }}</router-link>
      </template>
    </AppHeader>

    <div class="sp-body">
      <div class="sp-card">
        <div class="settings-tabs">
          <button :class="['settings-tab', {active: settingsTab === 'settings'}]" @click="settingsTab = 'settings'">{{ t('Settings') }}</button>
          <button :class="['settings-tab', {active: settingsTab === 'scoring'}]" @click="settingsTab = 'scoring'">{{ t('Scoring') }}</button>
          <button :class="['settings-tab', {active: settingsTab === 'backup'}]" @click="settingsTab = 'backup'">{{ t('Backup') }}</button>
        </div>

        <!-- Settings tab -->
        <div v-if="settingsTab === 'settings'" class="modal-body">
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Extraction Model') }}</div>
            <label class="field-row">
              <span class="field-label" :title="t('OpenAI-compatible API base URL')">{{ t('Base URL') }}</span>
              <input v-model="form.extraction_base_url" class="field-input" placeholder="https://api.openai.com/v1" />
            </label>
            <label class="field-row">
              <span class="field-label" :title="t('API key for the extraction model endpoint')">{{ t('API Key') }}</span>
              <input v-model="form.extraction_api_key" class="field-input" type="password"
                :placeholder="form.extraction_api_key === KEY_SENTINEL ? t('●●●●●● (saved — leave to keep)') : t('sk-… (enter to set)')" />
            </label>
            <label class="field-row">
              <span class="field-label" :title="t('Model name used to extract memories from session transcripts')">{{ t('Model') }}</span>
              <div class="combobox-wrap">
                <input v-model="form.extraction_model" class="field-input combobox-input"
                  placeholder="gpt-4o-mini" autocomplete="off"
                  @focus="onModelFocus" @blur="onModelBlur"
                  @input="modelHighlight = -1" @keydown="onModelKeydown" />
                <IconChevron v-if="availableModels.length" class="combobox-chevron" :class="{open: modelDropOpen}" width="10" height="10" />
                <div v-if="modelDropOpen && modelFilteredList.length" class="combobox-dropdown">
                  <div v-for="(m, i) in modelFilteredList" :key="m"
                    :class="['combobox-option', {highlighted: i === modelHighlight, selected: m === form.extraction_model}]"
                    @mousedown.prevent="selectModel(m)">
                    <span class="combobox-check">
                      <IconCheck v-if="m === form.extraction_model" width="11" height="11" />
                    </span>
                    {{ m }}
                  </div>
                </div>
              </div>
              <button class="btn-fetch-models" @click.prevent="fetchModels" :disabled="!form.extraction_base_url || isFetchingModels">
                <IconFetchRefresh v-if="!isFetchingModels" width="11" height="11" />
                <svg v-else width="11" height="11" viewBox="0 0 11 11" fill="none" class="spinning">
                  <circle cx="5.5" cy="5.5" r="4" stroke="currentColor" stroke-width="1.4" stroke-dasharray="6 14" stroke-linecap="round"/>
                </svg>
              </button>
            </label>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Hooks') }}</div>
            <label class="field-row">
              <span class="field-label" :title="t('Minimum seconds between two ingest triggers for the same session')">{{ t('Ingest cooldown') }}</span>
              <input v-model="form.hook_cooldown_sec" class="field-input" :placeholder="t('300 (seconds)')" />
            </label>
            <label class="field-row">
              <span class="field-label" :title="t('Minimum number of new user turns required to trigger ingest')">{{ t('Min turns') }}</span>
              <input v-model="form.hook_min_turns" class="field-input" placeholder="1" />
            </label>
            <label class="field-row">
              <span class="field-label" :title="t('Max tokens of memory context injected into each prompt via the UserPromptSubmit hook')">{{ t('Context tokens') }}</span>
              <input v-model="form.hook_budget_tokens" class="field-input" placeholder="1500" />
            </label>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('MCP / Service') }}</div>
            <label class="field-row">
              <span class="field-label" :title="t('Default number of memories returned by search_memory when top_k is not specified by the caller')">{{ t('Search top_k') }}</span>
              <input v-model="form.search_top_k" class="field-input" placeholder="3" />
            </label>
            <label class="field-row">
              <span class="field-label" :title="t('Cosine similarity threshold (0–1) above which an existing memory is considered a duplicate on save')">{{ t('Dup threshold') }}</span>
              <input v-model="form.dup_threshold" class="field-input" placeholder="0.92" />
            </label>
          </div>
        </div>

        <!-- Scoring tab -->
        <div v-else-if="settingsTab === 'scoring'" class="modal-body scoring-body">
          <div class="settings-group">
            <div class="settings-group-title">
              {{ t('Hybrid Score Weights') }}
              <span class="weight-sum-badge" :class="weightSumOk ? 'ok' : 'err'">Σ = {{ weightSum }}</span>
            </div>
            <div class="score-row"><span class="score-lbl">{{ t('Cosine') }}</span><input type="range" min="0" max="1" step="0.01" v-model="form.score_cosine_weight" class="score-slider" /><input type="number" min="0" max="1" step="0.01" v-model="form.score_cosine_weight" class="score-num" /></div>
            <div class="score-row"><span class="score-lbl">{{ t('Importance') }}</span><input type="range" min="0" max="1" step="0.01" v-model="form.score_importance_weight" class="score-slider" /><input type="number" min="0" max="1" step="0.01" v-model="form.score_importance_weight" class="score-num" /></div>
            <div class="score-row"><span class="score-lbl">{{ t('Recency') }}</span><input type="range" min="0" max="1" step="0.01" v-model="form.score_recency_weight" class="score-slider" /><input type="number" min="0" max="1" step="0.01" v-model="form.score_recency_weight" class="score-num" /></div>
            <div class="weight-bar">
              <div class="wb-seg wb-cosine" :style="{flex: wf('score_cosine_weight', 0.6)}"><span v-if="wf('score_cosine_weight', 0.6) >= 0.14">{{ t('Cosine') }}</span></div>
              <div class="wb-seg wb-importance" :style="{flex: wf('score_importance_weight', 0.3)}"><span v-if="wf('score_importance_weight', 0.3) >= 0.10">{{ t('Imp.') }}</span></div>
              <div class="wb-seg wb-recency" :style="{flex: wf('score_recency_weight', 0.1)}"><span v-if="wf('score_recency_weight', 0.1) >= 0.07">{{ t('Rec.') }}</span></div>
            </div>
            <div v-if="!weightSumOk" class="score-warn"><IconWarn width="12" height="12" /> {{ t('Weights should sum to 1.0') }} ({{ t('current') }}: {{ weightSum }})</div>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Recency Decay') }}</div>
            <div class="score-row"><span class="score-lbl">{{ t('Half-life (days)') }}</span><input type="range" min="1" max="365" step="1" v-model="form.score_recency_half_life" class="score-slider" /><input type="number" min="1" max="365" step="1" v-model="form.score_recency_half_life" class="score-num" /></div>
            <div class="score-hint">30d → {{ decayPct(30) }}% &nbsp;·&nbsp; 60d → {{ decayPct(60) }}% &nbsp;·&nbsp; 180d → {{ decayPct(180) }}%</div>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Type Multipliers') }}</div>
            <div v-for="tp in ['feedback','project','user','reference']" :key="tp" class="score-row">
              <span class="score-lbl type-lbl">{{ t(tp) }}</span>
              <div class="type-bar-track"><div class="type-bar-fill" :style="{width: typeBarPct(form['score_type_' + tp])}"></div></div>
              <input type="number" min="0.1" max="3" step="0.1" v-model="form['score_type_' + tp]" class="score-num" />
            </div>
            <div class="score-hint">{{ t('1.0 = neutral · >1.0 boosts rank · <1.0 reduces rank') }}</div>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Reranker') }}</div>
            <div class="score-row">
              <span class="score-lbl">{{ t('Enabled') }}</span>
              <label class="score-toggle">
                <input type="checkbox" :checked="form.rerank_enabled === 'true'" @change="form.rerank_enabled = $event.target.checked ? 'true' : 'false'" />
                <span class="score-toggle-track"><span class="score-toggle-thumb"></span></span>
              </label>
              <span class="score-toggle-state">{{ form.rerank_enabled === 'true' ? t('On') : t('Off') }}</span>
            </div>
            <div class="score-row" :class="{dimmed: form.rerank_enabled !== 'true'}">
              <span class="score-lbl">{{ t('Blend ratio') }}</span>
              <input type="range" min="0" max="1" step="0.05" v-model="form.score_rerank_blend" class="score-slider" :disabled="form.rerank_enabled !== 'true'" />
              <input type="number" min="0" max="1" step="0.05" v-model="form.score_rerank_blend" class="score-num" :disabled="form.rerank_enabled !== 'true'" />
            </div>
            <div class="score-hint" v-if="form.rerank_enabled === 'true'">
              final = {{ blendFmt }}×{{ t('reranker') }} + {{ counterBlendFmt }}×{{ t('hybrid') }}
            </div>
          </div>
        </div>

        <!-- Backup tab -->
        <div v-else class="modal-body backup-tab-body">
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Export') }}</div>
            <p class="backup-desc">{{ t('Download a full SQL backup of the database (pg_dump).') }}</p>
            <button class="btn-save backup-action-btn" @click="exportMemories">
              <IconDownload width="11" height="11" />
              {{ t('Download Backup') }}
            </button>
          </div>
          <div class="settings-group">
            <div class="settings-group-title">{{ t('Restore') }}</div>
            <p class="backup-desc">{{ t('Upload a .sql file to restore the database. Existing data will be overwritten.') }}</p>
            <input ref="importFileRef" type="file" accept=".sql" style="display:none" @change="onImportFile" />
            <button class="btn-save backup-action-btn" @click="openImport">
              <IconUpload width="11" height="11" />
              {{ t('Select .sql file…') }}
            </button>
          </div>
        </div>

        <div class="modal-footer">
          <template v-if="settingsTab === 'settings'">
            <span :class="['save-hint', saveHint.startsWith('Error') ? 'err' : 'ok']" v-if="saveHint">{{ saveHint }}</span>
            <button class="btn-cancel" @click="router.push('/memories')">{{ t('Cancel') }}</button>
            <button class="btn-save" @click="saveSettings" :disabled="isSaving">{{ isSaving ? t('Saving…') : t('Save') }}</button>
          </template>
          <template v-else>
            <button class="btn-cancel" @click="router.push('/memories')">{{ t('Close') }}</button>
          </template>
        </div>
      </div>
    </div>

    <!-- Import confirm dialog -->
    <Teleport to="body">
      <div v-if="importModalOpen" class="modal-overlay">
        <div class="modal modal-sm">
          <div class="modal-header">
            <span class="modal-title">{{ t('Import Memories') }}</span>
            <button class="modal-close" @click="importModalOpen = false">
              <IconClose width="12" height="12" />
            </button>
          </div>
          <div class="modal-body delete-modal-body">
            <template v-if="!importProgress.running && importProgress.total === 0">
              <p class="delete-confirm-text">{{ importPreview?.name }}</p>
              <p class="delete-confirm-sub">{{ t('This will overwrite existing data.') }}</p>
            </template>
            <template v-else-if="importProgress.running">
              <p class="delete-confirm-text">{{ t('Restoring…') }}</p>
            </template>
            <template v-else-if="importProgress.total === 1">
              <IconCheckLg width="32" height="32" style="color:var(--green);opacity:0.8" />
              <p class="delete-confirm-text">{{ t('Restored ✓') }}</p>
            </template>
            <template v-else-if="importProgress.total === -1">
              <p class="delete-confirm-text" style="color:var(--red)">{{ t('Restore failed') }}</p>
              <pre class="delete-confirm-sub" style="white-space:pre-wrap;font-size:11px;max-height:120px;overflow-y:auto">{{ importProgress.errorMsg }}</pre>
            </template>
          </div>
          <div class="modal-footer">
            <button class="btn-cancel" @click="importModalOpen = false">{{ importProgress.total !== 0 ? t('Close') : t('Cancel') }}</button>
            <button v-if="importProgress.total === 0" class="btn-save" @click="confirmImport" :disabled="importProgress.running">{{ t('Import') }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.sp-app {
  width: 100%; min-height: 100svh;
  display: flex; flex-direction: column;
  box-sizing: border-box;
  padding: 12px;
  gap: 12px;
}
.sp-body {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 8px;
}
.sp-card {
  width: min(640px, 100%);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  box-shadow: 0 4px 24px var(--shadow);
  overflow: hidden;
}
.score-warn { display: flex; align-items: center; gap: 4px; font-size: 10.5px; color: #e05050; font-weight: 500; padding-left: 86px; margin-top: 2px; }
</style>
