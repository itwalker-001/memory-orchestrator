<template>
  <div class="app">
    <AppHeader :loginOpen="loginOpen" @logout="logout" />

    <!-- Query bar -->
    <n-card size="small" :bordered="true" class="toolbar-card">
      <div class="toolbar">
        <n-select
          v-model:value="selectedProject"
          :options="projectOptions"
          size="small"
          style="width:200px"
          :placeholder="t('— Select project —')"
        />
        <n-radio-group v-model:value="selectedType" size="small">
          <n-radio-button value="">{{ t('All') }}</n-radio-button>
          <n-radio-button v-for="tp in TYPES" :key="tp" :value="tp">{{ t(tp) }}</n-radio-button>
        </n-radio-group>
        <div class="topk">
          <n-text depth="3" style="font-size:12px">top_k</n-text>
          <n-input-number v-model:value="topK" size="small" :min="1" :max="50" style="width:96px" />
        </div>
        <n-input
          v-model:value="queryText"
          size="small"
          clearable
          :placeholder="t('Enter a query to simulate MCP recall…')"
          style="flex:1;min-width:240px"
          @keydown.enter="runRecall"
        >
          <template #prefix><n-icon><IconSearch /></n-icon></template>
        </n-input>
        <n-button
          size="small"
          type="primary"
          :loading="isLoading"
          :disabled="!selectedProject || !queryText.trim()"
          @click="runRecall"
        >
          <template #icon><n-icon><IconActivity /></n-icon></template>
          {{ t('Run recall') }}
        </n-button>
      </div>
    </n-card>

    <!-- Intro hint (before first run) -->
    <n-card v-if="!hasRun" size="small" :bordered="false" class="hint-card">
      <n-text depth="3" style="font-size:13px">
        {{ t('This page replays the exact semantic recall an MCP search_memory call performs: it embeds your query, runs vector search with hybrid scoring (cosine + importance + recency), and ranks the hits. It does not record hit counts.') }}
      </n-text>
    </n-card>

    <!-- Results -->
    <div v-else class="table-wrap">
      <div class="result-meta">
        <n-text depth="3" style="font-size:12px">
          {{ t('{n} hits for', { n: hits.length }) }}
          <n-text strong>"{{ lastQuery }}"</n-text>
          · top_k {{ lastTopK }}
        </n-text>
      </div>
      <n-empty v-if="!isLoading && hits.length === 0" :description="t('No memories recalled — try a different query or project')" style="padding:48px 0" />
      <n-data-table
        v-else
        flex-height
        size="small"
        :columns="columns"
        :data="hits"
        :row-key="row => row.id"
        :loading="isLoading"
        :row-props="rowProps"
        style="height:100%"
      />
    </div>
  </div>

  <!-- Login -->
  <BaseModal :show="loginOpen">
    <n-card style="width:380px" :bordered="false" role="dialog">
      <div class="login-logo">
        <BrandLogo :size="28" />
        <span class="login-title">Memory Orchestrator</span>
      </div>
      <p class="login-subtitle">{{ t('Enter your UI admin token to continue') }}</p>
      <n-form @submit.prevent="submitLogin">
        <n-input
          v-model:value="loginInput"
          type="password"
          show-password-on="click"
          :placeholder="t('Paste token here…')"
          @keydown.enter="submitLogin"
        />
        <n-text v-if="loginError" type="error" style="display:block;margin-top:8px;font-size:12px">{{ loginError }}</n-text>
        <n-button type="primary" block style="margin-top:12px" :loading="loginLoading" :disabled="!loginInput" @click="submitLogin">
          <template #icon><n-icon><IconLogout /></n-icon></template>
          {{ t('Sign in') }}
        </n-button>
      </n-form>
    </n-card>
  </BaseModal>

  <MemoryDetailModal :memory="detailTarget" @close="detailTarget = null" />
</template>

<script setup>
import { ref, computed, h, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import {
  NCard, NSelect, NInput, NInputNumber, NButton, NRadioGroup, NRadioButton,
  NDataTable, NForm, NText, NIcon, NEmpty, NProgress,
} from 'naive-ui'
import { apiFetch } from './api.js'
import { useAppStore } from './stores/app.js'
import AppHeader from './AppHeader.vue'
import BaseModal from './BaseModal.vue'
import MemoryDetailModal from './MemoryDetailModal.vue'
import BrandLogo from './BrandLogo.vue'
import { IconSearch, IconActivity, IconLogout } from './icons.js'

const TYPES = ['user', 'feedback', 'project', 'reference']
const LS_PROJECT_KEY = 'mo_selected_project'

const appStore = useAppStore()
const { isDark, loginOpen, loginInput, loginError, loginLoading } = storeToRefs(appStore)
const { t } = appStore

const projects = ref([])
const projectMap = computed(() => Object.fromEntries(projects.value.map(p => [p.id, p.display_name || p.slug])))
const projectOptions = computed(() => projects.value.map(p => ({ label: p.display_name || p.slug, value: p.slug })))
const selectedProject = ref(localStorage.getItem(LS_PROJECT_KEY) || '')
const selectedType = ref('')
const topK = ref(5)
const queryText = ref('')

const hits = ref([])
const hasRun = ref(false)
const isLoading = ref(false)
const lastQuery = ref('')
const lastTopK = ref(5)
const detailTarget = ref(null)

async function submitLogin() {
  const ok = await appStore.submitLogin()
  if (ok) await loadProjects()
}

async function logout() {
  await appStore.logout()
  projects.value = []
  hits.value = []
  hasRun.value = false
}

async function loadProjects() {
  const res = await apiFetch('/projects')
  if (res.status === 401) { loginOpen.value = true; return }
  projects.value = await res.json()
  const slugs = projects.value.map(p => p.slug)
  if (!selectedProject.value || !slugs.includes(selectedProject.value)) {
    if (projects.value.length > 0) selectedProject.value = projects.value[0].slug
  }
}

async function runRecall() {
  if (!selectedProject.value || !queryText.value.trim()) return
  isLoading.value = true
  hasRun.value = true
  try {
    const params = new URLSearchParams()
    params.set('query', queryText.value.trim())
    params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    if (topK.value != null) params.set('top_k', String(topK.value))
    const res = await apiFetch(`/recall-test?${params}`)
    if (res.status === 401) { loginOpen.value = true; return }
    const data = await res.json()
    hits.value = (data.hits || []).map((hHit, i) => ({ ...hHit, rank: i + 1 }))
    lastQuery.value = data.query
    lastTopK.value = data.top_k
  } finally {
    isLoading.value = false
  }
}

// ── Display helpers ──
function projectDisplayName(id) { return projectMap.value[id] || '' }

const TYPE_PILL = {
  project:   { light: ['#E6F4EA', '#137333'], dark: ['#0F5B3E', '#86EFAC'] },
  feedback:  { light: ['#E7F3EF', '#287D63'], dark: ['#10463A', '#6EE7B7'] },
  reference: { light: ['#FBF1E3', '#B45309'], dark: ['#4A3410', '#FCD34D'] },
  user:      { light: ['#F1F3F5', '#475467'], dark: ['#27272A', '#A1A1AA'] },
}
function typePillStyle(type) {
  const pair = TYPE_PILL[type] || TYPE_PILL.user
  const [bg, fg] = isDark.value ? pair.dark : pair.light
  return `display:inline-block;background:${bg};color:${fg};font-size:11px;font-weight:500;line-height:1;padding:4px 9px;border-radius:4px;letter-spacing:0.02em`
}

// score / similarity → color cue (green strong, amber mid, red weak)
function scoreColor(v) {
  if (v >= 0.6) return '#18a058'
  if (v >= 0.4) return '#f0a020'
  return '#d03050'
}

const columns = computed(() => [
  { title: '#', key: 'rank', width: 48, align: 'center', render: row => h('span', { style: 'opacity:0.6' }, row.rank) },
  {
    title: t('Score'), key: 'score', width: 130,
    render: row => h('div', { style: 'display:flex;align-items:center;gap:8px' }, [
      h(NProgress, {
        type: 'line', percentage: Math.round(Math.max(0, Math.min(1, row.score)) * 100),
        height: 6, showIndicator: false, color: scoreColor(row.score),
        railColor: 'rgba(128,128,128,0.18)', style: 'width:56px',
      }),
      h('span', { style: `font-variant-numeric:tabular-nums;font-size:12px;color:${scoreColor(row.score)}` }, row.score.toFixed(3)),
    ]),
  },
  {
    title: t('Cosine'), key: 'cosine_sim', width: 88,
    render: row => h('span', { style: 'font-variant-numeric:tabular-nums;font-size:12px;opacity:0.8' }, row.cosine_sim.toFixed(3)),
  },
  { title: t('Type'), key: 'type', width: 104, render: row => h('span', { style: typePillStyle(row.type) }, t(row.type)) },
  { title: t('Name'), key: 'name', minWidth: 180, ellipsis: { tooltip: true } },
  { title: t('Description'), key: 'description', minWidth: 260, ellipsis: { tooltip: true } },
  {
    title: t('Project'), key: 'project', width: 140, ellipsis: { tooltip: true },
    render: row => projectDisplayName(row.project_id) || '—',
  },
])

function rowProps(row) {
  return { style: 'cursor:pointer', onClick: () => { detailTarget.value = row } }
}

onMounted(async () => {
  const res = await apiFetch('/projects')
  if (res.status === 401) { loginOpen.value = true; return }
  projects.value = await res.json()
  const slugs = projects.value.map(p => p.slug)
  if (!selectedProject.value || !slugs.includes(selectedProject.value)) {
    if (projects.value.length > 0) selectedProject.value = projects.value[0].slug
  }
})
</script>

<style scoped>
.app {
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
.toolbar { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.topk { display: flex; align-items: center; gap: 6px; }
.hint-card { margin-top: 4px; }
.table-wrap { flex: 1; min-height: 0; display: flex; flex-direction: column; gap: 6px; }
.result-meta { padding: 2px 2px 0; }
.login-logo { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.login-title { font-size: 16px; font-weight: 700; }
.login-subtitle { font-size: 12px; opacity: 0.7; margin-bottom: 14px; }
</style>
