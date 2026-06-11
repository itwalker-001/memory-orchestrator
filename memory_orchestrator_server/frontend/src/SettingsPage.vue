<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import {
  NCard, NTabs, NTabPane, NForm, NFormItem, NInput, NSelect, NButton,
  NSlider, NInputNumber, NSwitch, NSpace, NText, NTag, NIcon, NDivider,
  useMessage,
} from 'naive-ui'
import AppHeader from './AppHeader.vue'
import BaseModal from './BaseModal.vue'
import { apiFetch, apiJSON } from './api.js'
import { useAppStore } from './stores/app.js'
import { IconDownload, IconUpload, IconSync } from './icons.js'

const router = useRouter()
const appStore = useAppStore()
const { t } = appStore
const message = useMessage()

// ── Settings form ──
const KEY_SENTINEL = '__keep__'
const settingsTab = ref('settings')
const isSaving = ref(false)
const form = ref({
  extraction_base_url: '', extraction_model: '', extraction_api_key: '',
  hook_cooldown_sec: '', hook_min_turns: '', hook_budget_tokens: '',
  search_top_k: '', dup_threshold: '',
  rerank_enabled: 'false', score_rerank_blend: '',
  score_cosine_weight: '', score_importance_weight: '', score_recency_weight: '',
  score_recency_half_life: '',
  score_type_feedback: '', score_type_project: '', score_type_user: '', score_type_reference: '',
})

// Numeric proxy: bind n-slider / n-input-number to the string-backed form.
const num = new Proxy({}, {
  get: (_, k) => { const v = parseFloat(form.value[k]); return Number.isFinite(v) ? v : null },
  set: (_, k, v) => { form.value[k] = (v === null || v === undefined) ? '' : String(v); return true },
})
const rerankOn = computed({
  get: () => form.value.rerank_enabled === 'true',
  set: v => { form.value.rerank_enabled = v ? 'true' : 'false' },
})

// ── Model select ──
const availableModels = ref([])
const isFetchingModels = ref(false)
const modelOptions = computed(() => availableModels.value.map(m => ({ label: m, value: m })))
async function fetchModels() {
  if (!form.value.extraction_base_url) return
  isFetchingModels.value = true
  try {
    const params = new URLSearchParams({ base_url: form.value.extraction_base_url })
    const key = form.value.extraction_api_key
    const headers = (key && key !== '***' && key !== KEY_SENTINEL) ? { 'X-Api-Key': key } : {}
    const models = await apiFetch(`/models?${params}`, { headers }).then(r => r.ok ? r.json() : [])
    availableModels.value = models
    if (!models.length) message.warning(t('No models returned'))
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
const blendFmt = computed(() => (parseFloat(form.value.score_rerank_blend) || 0.8).toFixed(2))
const counterBlendFmt = computed(() => (1 - (parseFloat(form.value.score_rerank_blend) || 0.8)).toFixed(2))

const TYPE_MULTIPLIERS = ['feedback', 'project', 'user', 'reference']

// ── API ──
async function load() {
  try {
    const r = await apiFetch('/settings')
    if (r.status === 401) { router.push('/memories'); return }
    const data = await r.json()
    form.value = { ...form.value, ...data, extraction_api_key: data.extraction_api_key === '***' ? KEY_SENTINEL : (data.extraction_api_key || '') }
    availableModels.value = []
  } catch {}
}

async function saveSettings() {
  isSaving.value = true
  try {
    const payload = Object.fromEntries(Object.entries(form.value).filter(([k, v]) => {
      if (k === 'extraction_api_key') return v !== KEY_SENTINEL && v !== ''
      return v !== ''
    }))
    await apiJSON('/settings', { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    message.success(t('Saved'))
  } finally { isSaving.value = false }
}

async function exportMemories() {
  const r = await apiFetch('/backup')
  if (!r.ok) { message.error('Backup failed: ' + (await r.text())); return }
  const blob = await r.blob()
  const cd = r.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : 'mo-backup.sql'
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
    const r = await apiFetch('/restore', { method: 'POST', body: fd })
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
  await fetch(`/api/logout`, { method: 'POST' })
  router.push('/memories')
}

onMounted(() => { load() })
</script>

<template>
  <div class="sp-app">
    <AppHeader :loginOpen="false" @logout="logout" />

    <div class="sp-body">
      <n-card class="sp-card" :bordered="true" size="small">
        <n-tabs v-model:value="settingsTab" type="line" animated>
          <template #suffix>
            <n-button v-if="settingsTab !== 'backup'" type="primary" size="small" :loading="isSaving" @click="saveSettings">{{ t('Save settings') }}</n-button>
          </template>
          <!-- Settings tab -->
          <n-tab-pane name="settings" :tab="t('Settings')">
            <n-form label-placement="top" :show-feedback="false" size="small" class="settings-panel">
              <section class="settings-section">
                <div class="section-heading">{{ t('LLM Interface') }}</div>
                <div class="settings-field-row llm-row">
                  <n-form-item :label="t('API Base URL')">
                    <n-input v-model:value="form.extraction_base_url" placeholder="https://api.openai.com/v1" />
                  </n-form-item>
                  <n-form-item :label="t('API Key')">
                    <n-input v-model:value="form.extraction_api_key" type="password" show-password-on="click"
                      :placeholder="form.extraction_api_key === KEY_SENTINEL ? t('●●●●●● (saved — leave to keep)') : t('sk-… (enter to set)')" />
                  </n-form-item>
                  <n-form-item :label="t('Model')">
                    <div class="model-control">
                      <n-select v-model:value="form.extraction_model" :options="modelOptions"
                        filterable tag clearable :placeholder="'gpt-4o-mini'" />
                      <n-button class="model-fetch" :loading="isFetchingModels" :disabled="!form.extraction_base_url" @click="fetchModels">
                        <template #icon><n-icon><IconSync /></n-icon></template>
                        {{ t('Fetch') }}
                      </n-button>
                    </div>
                  </n-form-item>
                </div>
              </section>

              <section class="settings-section">
                <div class="section-heading">{{ t('Ingestion & Strategy') }}</div>
                <div class="settings-field-row strategy-row">
                  <n-form-item :label="t('Ingest cooldown')">
                    <n-input v-model:value="form.hook_cooldown_sec" :placeholder="t('300 (seconds)')" />
                  </n-form-item>
                  <n-form-item :label="t('Min Rounds')">
                    <n-input v-model:value="form.hook_min_turns" placeholder="1" />
                  </n-form-item>
                  <n-form-item :label="t('Context Tokens')">
                    <n-input v-model:value="form.hook_budget_tokens" placeholder="1500" />
                  </n-form-item>
                </div>
              </section>

              <section class="settings-section mcp-section">
                <div class="section-heading">{{ t('MCP / Service') }}</div>
                <div class="settings-field-row mcp-row">
                  <n-form-item :label="t('Search top_k')">
                    <n-input v-model:value="form.search_top_k" placeholder="3" />
                  </n-form-item>
                  <n-form-item :label="t('Dup threshold')">
                    <n-input v-model:value="form.dup_threshold" placeholder="0.92" />
                  </n-form-item>
                </div>
              </section>

              <section class="settings-section">
                <div class="section-heading">{{ t('Scoring') }}</div>
                <n-divider class="sp-subdivider" title-placement="left" style="margin:4px 0 8px">
                  <n-space align="center" :size="8">
                    <span>{{ t('Hybrid Score Weights') }}</span>
                    <n-tag size="small" :type="weightSumOk ? 'success' : 'error'" :bordered="false">Σ = {{ weightSum }}</n-tag>
                  </n-space>
                </n-divider>
                <div v-for="row in [
                    { key: 'score_cosine_weight', lbl: t('Cosine') },
                    { key: 'score_importance_weight', lbl: t('Importance') },
                    { key: 'score_recency_weight', lbl: t('Recency') },
                  ]" :key="row.key" class="sp-row">
                  <span class="sp-lbl">{{ row.lbl }}</span>
                  <n-slider v-model:value="num[row.key]" :min="0" :max="1" :step="0.01" style="flex:1" />
                  <n-input-number v-model:value="num[row.key]" :min="0" :max="1" :step="0.01" size="small" style="width:110px" />
                </div>
                <n-text v-if="!weightSumOk" depth="3" style="font-size:11px;color:#e05050">
                  {{ t('Weights should sum to 1.0') }} ({{ t('current') }}: {{ weightSum }})
                </n-text>

                <n-divider class="sp-subdivider" title-placement="left" style="margin:18px 0 8px">{{ t('Recency Decay') }}</n-divider>
                <div class="sp-row">
                  <span class="sp-lbl">{{ t('Half-life (days)') }}</span>
                  <n-slider v-model:value="num.score_recency_half_life" :min="1" :max="365" :step="1" style="flex:1" />
                  <n-input-number v-model:value="num.score_recency_half_life" :min="1" :max="365" :step="1" size="small" style="width:110px" />
                </div>
                <n-text depth="3" style="font-size:11px">
                  30d → {{ decayPct(30) }}% · 60d → {{ decayPct(60) }}% · 180d → {{ decayPct(180) }}%
                </n-text>

                <n-divider class="sp-subdivider" title-placement="left" style="margin:18px 0 8px">{{ t('Type Multipliers') }}</n-divider>
                <div v-for="tp in TYPE_MULTIPLIERS" :key="tp" class="sp-row">
                  <span class="sp-lbl">{{ t(tp) }}</span>
                  <n-slider v-model:value="num['score_type_' + tp]" :min="0.1" :max="3" :step="0.1" style="flex:1" />
                  <n-input-number v-model:value="num['score_type_' + tp]" :min="0.1" :max="3" :step="0.1" size="small" style="width:110px" />
                </div>
                <n-text depth="3" style="font-size:11px">{{ t('1.0 = neutral · >1.0 boosts rank · <1.0 reduces rank') }}</n-text>

                <n-divider class="sp-subdivider" title-placement="left" style="margin:18px 0 8px">{{ t('Reranker') }}</n-divider>
                <div class="sp-row">
                  <span class="sp-lbl">{{ t('Enabled') }}</span>
                  <n-switch v-model:value="rerankOn" />
                  <n-text depth="3" style="font-size:12px">{{ rerankOn ? t('On') : t('Off') }}</n-text>
                </div>
                <div class="sp-row" :style="{ opacity: rerankOn ? 1 : 0.45 }">
                  <span class="sp-lbl">{{ t('Blend ratio') }}</span>
                  <n-slider v-model:value="num.score_rerank_blend" :min="0" :max="1" :step="0.05" :disabled="!rerankOn" style="flex:1" />
                  <n-input-number v-model:value="num.score_rerank_blend" :min="0" :max="1" :step="0.05" :disabled="!rerankOn" size="small" style="width:110px" />
                </div>
                <n-text v-if="rerankOn" depth="3" style="font-size:11px">
                  final = {{ blendFmt }}×{{ t('reranker') }} + {{ counterBlendFmt }}×{{ t('hybrid') }}
                </n-text>
              </section>
            </n-form>
          </n-tab-pane>

          <!-- Backup tab -->
          <n-tab-pane name="backup" :tab="t('Backup')">
            <div class="backup-grid">
              <section class="settings-section">
                <div class="section-heading">{{ t('Export') }}</div>
                <n-text depth="3" tag="p" class="section-copy">{{ t('Download a full SQL backup of the database (pg_dump).') }}</n-text>
                <n-button @click="exportMemories">
                  <template #icon><n-icon><IconDownload /></n-icon></template>
                  {{ t('Download Backup') }}
                </n-button>
              </section>

              <section class="settings-section">
                <div class="section-heading">{{ t('Restore') }}</div>
                <n-text depth="3" tag="p" class="section-copy">{{ t('Upload a .sql file to restore the database. Existing data will be overwritten.') }}</n-text>
                <input ref="importFileRef" type="file" accept=".sql" style="display:none" @change="onImportFile" />
                <n-button @click="openImport">
                  <template #icon><n-icon><IconUpload /></n-icon></template>
                  {{ t('Select .sql file…') }}
                </n-button>
              </section>
            </div>
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </div>

    <!-- Import confirm dialog -->
    <BaseModal :show="importModalOpen" @close="importModalOpen = false">
      <n-card v-if="importModalOpen" :title="t('Import Memories')" closable style="width:440px" :bordered="false" @close="importModalOpen = false">
        <template v-if="!importProgress.running && importProgress.total === 0">
          <n-text strong style="display:block;word-break:break-all">{{ importPreview?.name }}</n-text>
          <n-text depth="3" tag="p" style="font-size:12px;margin-top:8px">{{ t('This will overwrite existing data.') }}</n-text>
        </template>
        <template v-else-if="importProgress.running">
          <n-text>{{ t('Restoring…') }}</n-text>
        </template>
        <template v-else-if="importProgress.total === 1">
          <n-text type="success" strong>{{ t('Restored ✓') }}</n-text>
        </template>
        <template v-else-if="importProgress.total === -1">
          <n-text type="error" strong style="display:block">{{ t('Restore failed') }}</n-text>
          <n-text depth="3" tag="pre" style="white-space:pre-wrap;font-size:11px;max-height:120px;overflow-y:auto;margin-top:6px">{{ importProgress.errorMsg }}</n-text>
        </template>
        <template #footer>
          <n-space justify="end">
            <n-button @click="importModalOpen = false">{{ importProgress.total !== 0 ? t('Close') : t('Cancel') }}</n-button>
            <n-button v-if="importProgress.total === 0" type="primary" :loading="importProgress.running" @click="confirmImport">{{ t('Import') }}</n-button>
          </n-space>
        </template>
      </n-card>
    </BaseModal>
  </div>
</template>

<style scoped>
.sp-app {
  width: 100%;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 8px 16px 18px;
  gap: 8px;
  font-family: Inter, "PingFang SC", "Microsoft YaHei", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.sp-body {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding-top: 12px;
}
.sp-card {
  width: min(900px, 100%);
  overflow: hidden;
}
.settings-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 8px 4px 4px;
}
.settings-section {
  border: 1px solid var(--n-border-color, var(--border));
  border-radius: 10px;
  padding: 14px 16px 16px;
  background: var(--n-color, var(--surface));
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.04);
}
.section-heading {
  display: flex;
  align-items: center;
  margin: 0 0 12px;
  font-size: 13px;
  font-weight: 700;
  color: var(--n-title-text-color, var(--text-primary));
}
.settings-field-row {
  display: grid;
  gap: 12px;
  align-items: end;
}
.llm-row {
  grid-template-columns: minmax(220px, 1.1fr) minmax(210px, 1fr) minmax(260px, 1.15fr);
}
.strategy-row {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}
.mcp-row {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
.model-control {
  display: flex;
  width: 100%;
}
.model-control :deep(.n-select) {
  flex: 1;
  min-width: 0;
}
.model-control :deep(.n-base-selection) {
  border-top-right-radius: 0 !important;
  border-bottom-right-radius: 0 !important;
}
.model-fetch {
  border-top-left-radius: 0;
  border-bottom-left-radius: 0;
  margin-left: -1px;
  min-width: 94px;
}
.mcp-section {
  margin-top: 2px;
}
.backup-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  padding-top: 4px;
}
.section-copy {
  display: block;
  min-height: 42px;
  margin: 0 0 14px;
  font-size: 12px;
  line-height: 1.5;
}
.settings-actions {
  width: 100%;
  padding: 4px 0 2px;
}
.sp-card :deep(.n-card__footer) {
  border-top: 1px solid var(--n-border-color, var(--border));
  position: sticky;
  bottom: 0;
  background: var(--n-color, var(--surface));
  z-index: 1;
}
.settings-panel :deep(.n-form-item-label) {
  font-weight: 600;
}
.settings-panel :deep(.n-input),
.settings-panel :deep(.n-base-selection) {
  border-radius: 8px;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04);
  transition: box-shadow 0.16s ease, border-color 0.16s ease;
}
.settings-panel :deep(.n-input:hover),
.settings-panel :deep(.n-base-selection:hover) {
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.06);
}
.settings-panel :deep(.n-input-wrapper),
.settings-panel :deep(.n-base-selection-label) {
  min-height: 34px;
}
.settings-panel :deep(.n-input__suffix) {
  display: flex;
  align-items: center;
}
.sp-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin: 8px 0;
}
.sp-lbl {
  width: 130px;
  flex-shrink: 0;
  font-size: 13px;
}
/* Scoring sub-headings: left-aligned to match section-heading rhythm. */
.sp-subdivider :deep(.n-divider__title) {
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: var(--n-title-text-color, var(--text-primary));
}
.sp-subdivider :deep(.n-divider__line--left) {
  width: 0;
  flex-basis: 0;
}
/* Tabular figures so digit columns don't jitter as values change. */
.settings-panel :deep(.n-input__input-el),
.settings-panel :deep(.n-input-number .n-input__input-el) {
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
@media (max-width: 860px) {
  .sp-body {
    padding-top: 4px;
  }
  .llm-row,
  .strategy-row,
  .mcp-row,
  .backup-grid {
    grid-template-columns: 1fr;
  }
  .settings-section {
    padding: 12px;
  }
  .model-control {
    flex-direction: column;
    gap: 8px;
  }
  .model-control :deep(.n-base-selection),
  .model-fetch {
    border-radius: 8px !important;
    margin-left: 0;
    width: 100%;
  }
}
</style>
