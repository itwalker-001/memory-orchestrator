<script setup>
import { ref, computed, onMounted } from 'vue'
import { BASE, apiFetch } from './api.js'
import enLocale from './locales/en.json'
import zhLocale from './locales/zh.json'
import IconClose from './icons/IconClose.svg'
import IconWarn from './icons/IconWarn.svg'
import IconChevron from './icons/IconChevron.svg'
import IconCheck from './icons/IconCheck.svg'
import IconFetchRefresh from './icons/IconFetchRefresh.svg'
import IconDownload from './icons/IconDownload.svg'
import IconUpload from './icons/IconUpload.svg'

const props = defineProps({
  open: { type: Boolean, required: true },
  lang: { type: String, default: 'en' },
})
const emit = defineEmits(['update:open', 'open-import'])

function t(key) { return ({ en: enLocale, zh: zhLocale }[props.lang] || enLocale)[key] ?? key }
function close() { emit('update:open', false) }

// ── Form state ──
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
  const data = await apiFetch(`${BASE}/settings`).then(r => r.json())
  form.value = { ...form.value, ...data, extraction_api_key: data.extraction_api_key === '***' ? KEY_SENTINEL : (data.extraction_api_key || '') }
  availableModels.value = []; modelDropOpen.value = false; modelHighlight.value = -1
  settingsTab.value = 'settings'; saveHint.value = ''
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
    setTimeout(() => { saveHint.value = ''; close() }, 1200)
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

onMounted(() => { load() })
defineExpose({ load })
</script>

<template>
  <div v-if="open" class="modal-overlay" @click.self="close">
    <div class="modal">
      <div class="modal-header">
        <span class="modal-title">{{ t('Advanced') }}</span>
        <button class="modal-close" @click="close">
          <IconClose width="12" height="12" />
        </button>
      </div>

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
          <button class="btn-save backup-action-btn" @click="exportMemories(); close()">
            <IconDownload width="11" height="11" />
            {{ t('Download Backup') }}
          </button>
        </div>
        <div class="settings-group">
          <div class="settings-group-title">{{ t('Restore') }}</div>
          <p class="backup-desc">{{ t('Upload a .sql file to restore the database. Existing data will be overwritten.') }}</p>
          <button class="btn-save backup-action-btn" @click="emit('open-import'); close()">
            <IconUpload width="11" height="11" />
            {{ t('Select .sql file…') }}
          </button>
        </div>
      </div>

      <div class="modal-footer">
        <template v-if="settingsTab === 'settings'">
          <span :class="['save-hint', saveHint.startsWith('Error') ? 'err' : 'ok']" v-if="saveHint">{{ saveHint }}</span>
          <button class="btn-cancel" @click="close">{{ t('Cancel') }}</button>
          <button class="btn-save" @click="saveSettings" :disabled="isSaving">{{ isSaving ? t('Saving…') : t('Save') }}</button>
        </template>
        <template v-else>
          <button class="btn-cancel" @click="close">{{ t('Close') }}</button>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: linear-gradient(90deg, rgba(0,212,138,0.06) 1px, transparent 1px),
    linear-gradient(0deg, rgba(0,212,138,0.06) 1px, transparent 1px), rgba(2,4,10,0.66);
  background-size: 28px 28px;
  display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(5px); animation: overlay-in 150ms ease;
}
@keyframes overlay-in { from { opacity: 0 } to { opacity: 1 } }
.modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg); width: 440px; max-width: 95vw;
  box-shadow: 0 24px 70px var(--shadow), 0 0 0 1px rgba(0,212,138,0.06), 0 0 40px -28px var(--glow);
  display: flex; flex-direction: column;
  animation: modal-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
}
@keyframes modal-in { from { opacity: 0; transform: scale(0.96) translateY(8px) } to { opacity: 1; transform: none } }
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 16px 12px; border-bottom: 1px solid var(--border-subtle);
  background: linear-gradient(90deg, var(--accent-dim), transparent 62%);
}
.modal-title { font-family: 'Orbitron', ui-monospace, monospace; font-size: 12px; font-weight: 700; color: var(--text-primary); letter-spacing: 0.08em; text-transform: uppercase; }
.modal-close { display: flex; align-items: center; justify-content: center; width: 24px; height: 24px; background: transparent; border: none; color: var(--text-muted); border-radius: var(--radius-sm); cursor: pointer; }
.modal-close:hover { background: var(--red-dim); color: var(--red); }
.settings-tabs { display: flex; border-bottom: 1px solid var(--border); padding: 0 12px; background: var(--surface-panel); }
.settings-tab { padding: 8px 14px; font-size: 12px; font-weight: 500; color: var(--muted); background: transparent; border: none; border-bottom: 2px solid transparent; cursor: pointer; margin-bottom: -1px; transition: color 0.15s, border-color 0.15s; }
.settings-tab:hover { color: var(--text); }
.settings-tab.active { color: var(--accent); border-bottom-color: var(--accent); }
.modal-body { padding: 12px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; max-height: calc(90vh - 120px); }
.scoring-body { padding: 12px; display: flex; flex-direction: column; gap: 12px; overflow-y: auto; max-height: calc(90vh - 120px); }
.backup-tab-body { padding: 16px; display: flex; flex-direction: column; gap: 20px; }
.backup-desc { font-size: 12px; color: var(--muted); margin: 0 0 10px; }
.backup-action-btn { display: inline-flex; align-items: center; gap: 6px; padding: 7px 14px; }
.settings-group { display: flex; flex-direction: column; gap: 8px; }
.settings-group-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em; color: var(--text-muted); display: flex; align-items: center; gap: 6px; }
.field-row { display: flex; align-items: center; gap: 8px; }
.field-label { font-size: 12px; color: var(--text-secondary); width: 80px; flex-shrink: 0; cursor: help; }
.field-input { flex: 1; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 5px 8px; font-size: 12px; color: var(--text-primary); font-family: inherit; min-width: 0; }
.field-input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-dim); outline: none; background: var(--surface); }
.field-input::placeholder { color: var(--text-muted); }
.modal-footer { display: flex; align-items: center; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border-subtle); }
.save-hint { font-size: 12px; margin-right: auto; }
.save-hint.ok { color: var(--green); }
.save-hint.err { color: var(--red); }
.btn-cancel { background: var(--surface-2); color: var(--text-secondary); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 6px 14px; font-size: 12px; cursor: pointer; }
.btn-save { background: var(--accent); color: #fff; border: none; border-radius: var(--radius-sm); padding: 6px 14px; font-size: 12px; font-weight: 600; cursor: pointer; }
.btn-save:disabled { opacity: 0.5; cursor: default; }
/* Scoring */
.score-row { display: flex; align-items: center; gap: 8px; }
.score-lbl { font-size: 11px; color: var(--text-muted); width: 78px; flex-shrink: 0; }
.score-slider { flex: 1; height: 4px; accent-color: var(--accent); cursor: pointer; }
.score-slider:disabled { opacity: 0.3; cursor: default; }
.score-num { width: 54px; background: var(--surface-2); border: 1px solid var(--border); border-radius: var(--radius-sm); padding: 3px 6px; font-size: 12px; color: var(--text-primary); font-family: inherit; text-align: right; }
.score-num:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-dim); outline: none; }
.score-num:disabled { opacity: 0.4; cursor: default; }
.score-hint { font-size: 10px; color: var(--text-muted); padding-left: 86px; margin-top: -2px; }
.score-warn { display: flex; align-items: center; gap: 4px; font-size: 10.5px; color: #e05050; font-weight: 500; padding-left: 86px; margin-top: 2px; }
.weight-sum-badge { font-size: 10.5px; font-weight: 700; padding: 1px 7px; border-radius: 20px; }
.weight-sum-badge.ok { background: var(--accent-dim); color: var(--accent); }
.weight-sum-badge.err { background: rgba(224,80,80,0.12); color: #e05050; }
.weight-bar { display: flex; height: 16px; border-radius: 4px; overflow: hidden; gap: 1px; margin: 4px 0 2px; }
.wb-seg { display: flex; align-items: center; justify-content: center; font-size: 9.5px; font-weight: 600; color: #fff; transition: flex 0.15s; min-width: 2px; }
.wb-cosine { background: #4a87e8; }
.wb-importance { background: #8a5bbf; }
.wb-recency { background: #2eb87a; }
.type-bar-track { flex: 1; height: 7px; background: var(--border-subtle); border-radius: 4px; overflow: hidden; }
.type-bar-fill { height: 100%; background: var(--accent); border-radius: 4px; transition: width 0.1s; }
.score-toggle { position: relative; display: inline-flex; align-items: center; width: 34px; height: 19px; flex-shrink: 0; }
.score-toggle input { opacity: 0; width: 0; height: 0; position: absolute; }
.score-toggle-track { position: absolute; inset: 0; background: var(--border); border-radius: 20px; transition: background 0.2s; }
.score-toggle-thumb { position: absolute; top: 2px; left: 2px; width: 15px; height: 15px; background: #fff; border-radius: 50%; transition: transform 0.2s; }
.score-toggle input:checked ~ .score-toggle-track { background: var(--accent); }
.score-toggle input:checked ~ .score-toggle-track .score-toggle-thumb { transform: translateX(15px); }
.score-toggle-state { font-size: 11px; color: var(--text-muted); min-width: 22px; }
.dimmed { opacity: 0.45; pointer-events: none; }
/* Combobox */
.combobox-wrap { position: relative; flex: 1; display: flex; align-items: center; }
.combobox-input { padding-right: 24px; }
.combobox-chevron { position: absolute; right: 7px; color: var(--text-muted); pointer-events: none; transition: transform var(--transition); }
.combobox-chevron.open { transform: rotate(180deg); }
.combobox-dropdown { position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 200; background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-md); box-shadow: 0 14px 34px var(--shadow); max-height: 200px; overflow-y: auto; padding: 4px; }
.combobox-option { display: flex; align-items: center; gap: 6px; padding: 6px 8px; border-radius: var(--radius-sm); font-size: 12px; color: var(--text-primary); cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.combobox-option:hover, .combobox-option.highlighted { background: var(--surface-2); }
.combobox-option.selected { color: var(--accent); }
.combobox-check { width: 16px; flex-shrink: 0; display: flex; align-items: center; }
.btn-fetch-models { display: flex; align-items: center; justify-content: center; width: 26px; height: 26px; flex-shrink: 0; background: var(--surface-2); color: var(--text-muted); border: 1px solid var(--border); border-radius: var(--radius-sm); cursor: pointer; }
.btn-fetch-models:hover:not(:disabled) { background: var(--accent-dim); color: var(--accent); }
.btn-fetch-models:disabled { opacity: 0.35; cursor: default; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 0.7s linear infinite; }
</style>
