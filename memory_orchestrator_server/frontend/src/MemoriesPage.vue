<template>
  <div class="app">
    <AppHeader
      :loginOpen="loginOpen"
      @logout="logout"
    />

    <!-- Toolbar -->
    <n-card size="small" :bordered="true" class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <n-select
            v-model:value="selectedProject"
            :options="projectOptions"
            size="small"
            style="width:200px"
            @update:value="load()"
          />
          <n-radio-group v-model:value="selectedType" size="small" @update:value="load()">
            <n-radio-button value="">{{ t('All') }}</n-radio-button>
            <n-radio-button v-for="tp in TYPES" :key="tp" :value="tp">{{ t(tp) }}</n-radio-button>
          </n-radio-group>
        </div>
        <div class="toolbar-right">
          <n-button size="small" @click="openDuplicates">
            <template #icon><n-icon><IconDuplicates /></n-icon></template>
            {{ t('Duplicates') }}
          </n-button>
          <n-button size="small" @click="openConflicts">
            <template #icon><n-icon><IconConflicts /></n-icon></template>
            {{ t('Conflicts') }}
          </n-button>
          <input ref="importFileRef" type="file" accept=".sql" style="display:none" @change="onImportFile" />
          <n-input
            v-model:value="searchText"
            size="small"
            clearable
            :placeholder="t('Search…')"
            style="width:200px"
          >
            <template #prefix><n-icon><IconSearch /></n-icon></template>
          </n-input>
          <n-button v-if="selectedProject || selectedType || searchText" size="small" quaternary @click="resetFilters">
            {{ t('Reset') }}
          </n-button>
          <n-button size="small" :loading="isLoading" @click="load">
            <template #icon><n-icon><IconRefresh /></n-icon></template>
            {{ t('Refresh') }}
          </n-button>
          <n-button size="small" type="primary" @click="openWrite" :title="t('New memory') + ' (N)'">
            <template #icon><n-icon><IconPlus /></n-icon></template>
            {{ t('New') }}
          </n-button>
        </div>
      </div>
    </n-card>

    <!-- Table -->
    <div class="table-wrap">
      <n-data-table
        flex-height
        size="small"
        :columns="columns"
        :data="filtered"
        :row-key="row => row.id"
        :loading="isLoading"
        :pagination="pagination"
        :row-props="rowProps"
        v-model:checked-row-keys="checkedKeys"
        style="height:100%"
      />
    </div>

    <!-- Bulk action bar -->
    <Transition name="bulk">
      <n-card v-if="checkedKeys.length > 0" size="small" class="bulk-bar" :bordered="true">
        <n-space align="center" :size="10">
          <n-text strong>{{ checkedKeys.length }} {{ t('selected') }}</n-text>
          <n-button size="tiny" quaternary @click="checkedKeys = []">×</n-button>
          <n-divider vertical />
          <template v-if="!bulkConfirmDelete">
            <n-button size="tiny" type="error" @click="bulkConfirmDelete = true">{{ t('Delete') }}</n-button>
          </template>
          <template v-else>
            <n-text>{{ t('Delete {n}?', {n: checkedKeys.length}) }}</n-text>
            <n-button size="tiny" type="error" :loading="isBulkDeleting" @click="bulkDelete">{{ t('Yes') }}</n-button>
            <n-button size="tiny" @click="bulkConfirmDelete = false">{{ t('No') }}</n-button>
          </template>
          <n-divider vertical />
          <n-select
            v-model:value="bulkMoveTarget"
            :options="moveOptions"
            size="tiny"
            :placeholder="t('Move to…')"
            style="width:160px"
          />
          <n-button size="tiny" :disabled="!bulkMoveTarget" :loading="isBulkMoving" @click="bulkMove">
            {{ t('Move') }}
          </n-button>
        </n-space>
      </n-card>
    </Transition>
  </div>

  <!-- ── Modals ── -->
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
        <n-button
          type="primary"
          block
          style="margin-top:12px"
          :loading="loginLoading"
          :disabled="!loginInput"
          @click="submitLogin"
        >
          <template #icon><n-icon><IconLogout /></n-icon></template>
          {{ t('Sign in') }}
        </n-button>
      </n-form>
    </n-card>
  </BaseModal>

  <MemoryDetailModal :memory="detailTarget" @close="detailTarget = null" @edit="m => { detailTarget = null; openEdit(m) }" />

  <!-- Edit / New memory (shared component) -->
  <MemoryEditModal
    :show="editModalShow"
    :memory="editModalMemory"
    :show-project="true"
    :projects="projects"
    :default-project-id="selectedProject"
    @close="editModalShow = false"
    @saved="onEditSaved"
  />

  <!-- Delete confirm -->
  <BaseModal :show="!!deleteTarget" :mask-closable="true" @close="deleteTarget = null">
    <n-card :title="t('Delete memory')" closable style="width:440px" :bordered="false" @close="deleteTarget = null">
      <n-text>{{ t('Delete {name}?', {name: ''}) }}<strong>{{ deleteTarget?.name }}</strong></n-text>
      <n-text depth="3" tag="p" style="margin-top:8px;font-size:12px">
        {{ t('This memory will be soft-deleted and removed from context injection.') }}
      </n-text>
      <template #footer>
        <n-space justify="end">
          <n-button @click="deleteTarget = null">{{ t('Cancel') }}</n-button>
          <n-button type="error" :loading="isDeleting" @click="confirmDelete">{{ t('Delete') }}</n-button>
        </n-space>
      </template>
    </n-card>
  </BaseModal>


  <!-- Clone -->
  <BaseModal :show="!!cloneSource" :mask-closable="true" @close="cloneSource = null">
    <n-card :title="t('Clone Memory')" closable style="width:480px" :bordered="false" @close="cloneSource = null">
      <template v-if="cloneSource">
        <n-card size="small" :bordered="true" style="margin-bottom:14px">
          <n-space align="center" :size="8" style="margin-bottom:6px">
            <n-tag size="small" :type="typeTagType(cloneSource.type)">{{ t(cloneSource.type) }}</n-tag>
            <n-text depth="3" style="font-size:12px">{{ projectDisplayName(cloneSource.project_id) || t('Global (*)') }}</n-text>
          </n-space>
          <n-text strong style="display:block">{{ cloneSource.name }}</n-text>
          <n-text v-if="cloneSource.description" depth="2" style="display:block;font-size:12px;margin-top:4px">{{ cloneSource.description }}</n-text>
        </n-card>
        <n-form-item :label="t('Clone to project')" :show-feedback="false">
          <n-select v-model:value="cloneSlug" :options="writeProjectOptions.filter(o => o.value)" :placeholder="t('— Select project —')" />
        </n-form-item>
        <n-text v-if="cloneError" type="error" style="display:block;margin-top:8px;font-size:12px">{{ cloneError }}</n-text>
        <n-text v-if="cloneDone" type="success" style="display:block;margin-top:8px;font-size:12px">{{ t('Cloned ✓') }}</n-text>
      </template>
      <template #footer>
        <n-space justify="end">
          <n-button @click="cloneSource = null">{{ t('Cancel') }}</n-button>
          <n-button type="primary" :disabled="!cloneSlug" :loading="isCloning" @click="doClone">{{ t('Clone') }}</n-button>
        </n-space>
      </template>
    </n-card>
  </BaseModal>

  <!-- Import -->
  <BaseModal :show="importModalOpen" :mask-closable="true" @close="importModalOpen = false">
    <n-card :title="t('Import Memories')" closable style="width:440px" :bordered="false" @close="importModalOpen = false">
      <template v-if="!importProgress.running && importProgress.total === 0">
        <n-text strong style="display:block">{{ importPreview?.name }}</n-text>
        <n-text depth="3" tag="p" style="margin-top:8px;font-size:12px">{{ t('This will overwrite existing data.') }}</n-text>
      </template>
      <template v-else-if="importProgress.running">
        <n-spin size="small" /> <n-text>{{ t('Restoring…') }}</n-text>
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

  <!-- Duplicates -->
  <BaseModal :show="duplicatesOpen" :mask-closable="true" @close="duplicatesOpen = false">
    <n-card closable style="width:min(1000px,94vw)" :bordered="false" @close="duplicatesOpen = false">
      <template #header>
        {{ t('Duplicates') }} <n-text v-if="!duplicatesLoading" depth="3">({{ duplicatePairs.length }})</n-text>
      </template>
      <template #header-extra>
        <n-space align="center" :size="12">
          <n-text depth="3" style="font-size:12px">{{ t('Threshold') }}</n-text>
          <n-slider v-model:value="duplicateThresholdNum" :min="0.80" :max="0.98" :step="0.01" style="width:160px" />
          <n-text style="font-size:12px;width:40px">{{ duplicateThreshold }}</n-text>
          <n-button size="small" :loading="duplicatesLoading" @click="scanDuplicates">{{ t('Scan') }}</n-button>
        </n-space>
      </template>
      <n-text v-if="duplicateError" type="error" style="display:block;margin-bottom:8px">{{ duplicateError }}</n-text>
      <n-scrollbar style="max-height:60vh">
        <n-empty v-if="!duplicatesLoading && duplicatePairs.length === 0" :description="t('No duplicates found')" style="padding:40px 0" />
        <div v-else class="dup-list">
          <n-card v-for="(pair, i) in duplicatePairs" :key="pair.id1 + pair.id2" size="small" :bordered="true" class="dup-pair">
            <div class="dup-side">
              <n-space align="center" :size="6" style="margin-bottom:4px">
                <n-tag size="small" :type="typeTagType(pair.type1)">{{ t(pair.type1) }}</n-tag>
                <n-text depth="3" style="font-size:11px">{{ projectSlugMap[pair.project_slug1] || pair.project_slug1 }}</n-text>
              </n-space>
              <n-text strong style="display:block">{{ pair.name1 }}</n-text>
              <n-text depth="2" style="display:block;font-size:12px">{{ pair.description1 }}</n-text>
              <n-text depth="3" style="display:block;font-size:11px;margin-top:4px">{{ pair.content1 }}</n-text>
              <n-button size="tiny" type="error" style="margin-top:6px" @click="deleteDupMem(pair.id1, i)">{{ t('Delete') }}</n-button>
            </div>
            <div class="dup-center">
              <n-text strong>{{ Math.round(pair.similarity * 100) }}%</n-text>
              <n-button size="tiny" quaternary @click="duplicatePairs.splice(i, 1)">{{ t('Skip') }}</n-button>
            </div>
            <div class="dup-side">
              <n-space align="center" :size="6" style="margin-bottom:4px">
                <n-tag size="small" :type="typeTagType(pair.type2)">{{ t(pair.type2) }}</n-tag>
                <n-text depth="3" style="font-size:11px">{{ projectSlugMap[pair.project_slug2] || pair.project_slug2 }}</n-text>
              </n-space>
              <n-text strong style="display:block">{{ pair.name2 }}</n-text>
              <n-text depth="2" style="display:block;font-size:12px">{{ pair.description2 }}</n-text>
              <n-text depth="3" style="display:block;font-size:11px;margin-top:4px">{{ pair.content2 }}</n-text>
              <n-button size="tiny" type="error" style="margin-top:6px" @click="deleteDupMem(pair.id2, i)">{{ t('Delete') }}</n-button>
            </div>
          </n-card>
        </div>
      </n-scrollbar>
    </n-card>
  </BaseModal>

  <!-- Conflicts -->
  <BaseModal :show="conflictsOpen" :mask-closable="true" @close="conflictsOpen = false">
    <n-card closable style="width:min(1000px,94vw)" :bordered="false" @close="conflictsOpen = false">
      <template #header>
        {{ t('Conflicts') }} <n-text v-if="!conflictsLoading" depth="3">({{ conflictPairs.length }})</n-text>
      </template>
      <template #header-extra>
        <n-space align="center" :size="12">
          <n-text depth="3" style="font-size:12px">{{ t('Min similarity') }}</n-text>
          <n-slider v-model:value="conflictMinSimNum" :min="0.40" :max="0.85" :step="0.01" style="width:160px" />
          <n-text style="font-size:12px;width:40px">{{ conflictMinSim }}</n-text>
          <n-button size="small" :loading="conflictsLoading" @click="scanConflicts">{{ t('Scan') }}</n-button>
        </n-space>
      </template>
      <n-text v-if="conflictError" type="error" style="display:block;margin-bottom:8px">{{ conflictError }}</n-text>
      <n-scrollbar style="max-height:60vh">
        <n-empty v-if="!conflictsLoading && conflictPairs.length === 0" :description="t('No conflicts found')" style="padding:40px 0" />
        <div v-else class="dup-list">
          <n-card v-for="(pair, i) in conflictPairs" :key="pair.id1 + pair.id2" size="small" :bordered="true" class="dup-pair">
            <div class="dup-side">
              <n-space align="center" :size="6" style="margin-bottom:4px">
                <n-tag size="small" :type="typeTagType(pair.type1)">{{ t(pair.type1) }}</n-tag>
                <n-text depth="3" style="font-size:11px">{{ projectSlugMap[pair.project_slug1] || pair.project_slug1 }}</n-text>
              </n-space>
              <n-text strong style="display:block">{{ pair.name1 }}</n-text>
              <n-text depth="2" style="display:block;font-size:12px">{{ pair.description1 }}</n-text>
              <n-text depth="3" style="display:block;font-size:11px;margin-top:4px">{{ pair.content1 }}</n-text>
              <n-button size="tiny" type="error" style="margin-top:6px" @click="deleteConflictMem(pair.id1)">{{ t('Delete') }}</n-button>
            </div>
            <div class="dup-center">
              <n-text strong>{{ Math.round(pair.similarity * 100) }}%</n-text>
              <n-button size="tiny" quaternary @click="conflictPairs.splice(i, 1)">{{ t('Skip') }}</n-button>
            </div>
            <div class="dup-side">
              <n-space align="center" :size="6" style="margin-bottom:4px">
                <n-tag size="small" :type="typeTagType(pair.type2)">{{ t(pair.type2) }}</n-tag>
                <n-text depth="3" style="font-size:11px">{{ projectSlugMap[pair.project_slug2] || pair.project_slug2 }}</n-text>
              </n-space>
              <n-text strong style="display:block">{{ pair.name2 }}</n-text>
              <n-text depth="2" style="display:block;font-size:12px">{{ pair.description2 }}</n-text>
              <n-text depth="3" style="display:block;font-size:11px;margin-top:4px">{{ pair.content2 }}</n-text>
              <n-button size="tiny" type="error" style="margin-top:6px" @click="deleteConflictMem(pair.id2)">{{ t('Delete') }}</n-button>
            </div>
          </n-card>
        </div>
      </n-scrollbar>
    </n-card>
  </BaseModal>
</template>

<script setup>
import { ref, computed, watch, reactive, h, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import {
  NCard, NSelect, NInput, NButton, NRadioGroup, NRadioButton, NDataTable,
  NTag, NForm, NFormItem, NSpace, NText, NDivider, NSlider, NScrollbar,
  NEmpty, NSpin, NIcon, useMessage,
} from 'naive-ui'
import { apiFetch, apiJSON, errText } from './api.js'
import { useAppStore } from './stores/app.js'
import AppHeader from './AppHeader.vue'
import BaseModal from './BaseModal.vue'
import MemoryDetailModal from './MemoryDetailModal.vue'
import MemoryEditModal from './MemoryEditModal.vue'
import BrandLogo from './BrandLogo.vue'
import {
  IconSearch, IconEdit, IconTrash, IconClone, IconPlus,
  IconRefresh, IconLogout, IconDuplicates, IconConflicts,
} from './icons.js'

const TYPES = ['user', 'feedback', 'project', 'reference']

const appStore = useAppStore()
const { isDark, lang, loginOpen, loginInput, loginError, loginLoading } = storeToRefs(appStore)
const { t } = appStore
const message = useMessage()

async function submitLogin() {
  const ok = await appStore.submitLogin()
  if (ok) {
    projects.value = await apiFetch(`/projects`).then(r => r.json())
    autoSelectProject()
    await load()
  }
}

async function logout() {
  await appStore.logout()
  memories.value = []
  projects.value = []
  stats.value = null
}

const projects = ref([])
const projectMap = computed(() => Object.fromEntries(projects.value.map(p => [p.id, p.display_name || p.slug])))
const projectSlugMap = computed(() => Object.fromEntries(projects.value.map(p => [p.slug, p.display_name || p.slug])))
const memories = ref([])
const stats = ref(null)
const LS_PROJECT_KEY = 'mo_selected_project'
const selectedProject = ref(localStorage.getItem(LS_PROJECT_KEY) || '')
watch(selectedProject, v => localStorage.setItem(LS_PROJECT_KEY, v))

const projectOptions = computed(() => [
  { label: t('All'), value: '' },
  ...projects.value.map(p => ({ label: p.display_name || p.slug, value: p.slug })),
])
// project select inside write/clone forms uses slug as the value
const writeProjectOptions = computed(() => [
  { label: t('Global (*)'), value: '' },
  ...projects.value.map(p => ({ label: p.display_name || p.slug, value: p.slug })),
])
const moveOptions = computed(() => projects.value.map(p => ({ label: p.display_name || p.slug, value: p.slug })))


function autoSelectProject() {
  const saved = localStorage.getItem(LS_PROJECT_KEY)
  const slugs = projects.value.map(p => p.slug)
  if (saved && slugs.includes(saved)) {
    selectedProject.value = saved
  } else if (projects.value.length > 0) {
    selectedProject.value = projects.value[0].slug
  }
}
const selectedType = ref('')
const searchText = ref('')
const detailTarget = ref(null)
const sortDesc = ref(true)
const sortBy = ref('time')
const isLoading = ref(false)

async function load() {
  isLoading.value = true
  try {
    const params = new URLSearchParams()
    if (selectedProject.value) params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    if (searchText.value) params.set('q', searchText.value)
    params.set('limit', '200')
    params.set('sort_by', sortBy.value)
    params.set('sort_desc', sortDesc.value ? 'true' : 'false')
    const [memsRes, stRes] = await Promise.all([
      apiFetch(`/memories?${params}`),
      apiFetch(`/stats${selectedProject.value ? '?project_slug=' + selectedProject.value : ''}`)
    ])
    if (memsRes.status === 401) { loginOpen.value = true; return }
    const [mems, st] = await Promise.all([memsRes.json(), stRes.json()])
    memories.value = mems
    stats.value = st
  } finally {
    isLoading.value = false
  }
}

const filtered = computed(() => memories.value)

let searchTimer = null
watch(searchText, () => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(load, 300)
})

// ── Delete ──
const deleteTarget = ref(null)
const isDeleting = ref(false)
function del(m) { deleteTarget.value = m }
async function confirmDelete() {
  if (!deleteTarget.value) return
  isDeleting.value = true
  try {
    await apiFetch(`/memories/${deleteTarget.value.id}`, { method: 'DELETE' })
    deleteTarget.value = null
    await load()
  } finally {
    isDeleting.value = false
  }
}

// ── Clone ──
const cloneSource = ref(null)
const cloneSlug = ref('')
const isCloning = ref(false)
const cloneError = ref('')
const cloneDone = ref(false)
function openClone(m) {
  cloneSource.value = m
  cloneSlug.value = ''
  cloneError.value = ''
  cloneDone.value = false
}
async function doClone() {
  if (!cloneSource.value || !cloneSlug.value) return
  isCloning.value = true
  cloneError.value = ''
  try {
    await apiJSON(`/memories/${cloneSource.value.id}/clone?project_slug=${encodeURIComponent(cloneSlug.value)}`, { method: 'POST', skipErrorToast: true })
    cloneDone.value = true
    await load()
    setTimeout(() => { cloneSource.value = null }, 1500)
  } catch (e) {
    cloneError.value = errText(e)
  } finally {
    isCloning.value = false
  }
}

// ── Edit / New memory (shared modal) ──
const editModalShow = ref(false)
const editModalMemory = ref(null)

function openEdit(m) {
  editModalMemory.value = m
  editModalShow.value = true
}

function openWrite() {
  editModalMemory.value = null
  editModalShow.value = true
}

async function onEditSaved() {
  editModalShow.value = false
  await load()
}

// ── Bulk operations ──
const checkedKeys = ref([])
const isBulkDeleting = ref(false)
const isBulkMoving = ref(false)
const bulkMoveTarget = ref('')
const bulkConfirmDelete = ref(false)

async function bulkDelete() {
  if (!checkedKeys.value.length) return
  isBulkDeleting.value = true
  try {
    const ids = [...checkedKeys.value]
    await apiJSON('/memories/batch-delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids }),
    })
    checkedKeys.value = []
    bulkConfirmDelete.value = false
    await load()
  } finally {
    isBulkDeleting.value = false
  }
}
async function bulkMove() {
  if (!bulkMoveTarget.value || !checkedKeys.value.length) return
  isBulkMoving.value = true
  try {
    const ids = [...checkedKeys.value]
    await apiJSON('/memories/batch-move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ids, project_slug: bulkMoveTarget.value }),
    })
    checkedKeys.value = []
    bulkMoveTarget.value = ''
    await load()
  } finally {
    isBulkMoving.value = false
  }
}

// ── Import / Export ──
const importFileRef = ref(null)
const importPreview = ref(null)
const importModalOpen = ref(false)
const importProgress = ref({ done: 0, total: 0, skipped: 0, errors: 0, running: false, errorMsg: '' })

async function exportMemories() {
  const r = await apiFetch('/backup')
  if (!r.ok) { message.error('Backup failed: ' + (await r.text())); return }
  const blob = await r.blob()
  const cd = r.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="([^"]+)"/)
  const filename = match ? match[1] : `mo-backup-${new Date().toISOString().slice(0, 10)}.sql`
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = filename
  document.body.appendChild(a); a.click(); document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
function openImport() { importFileRef.value?.click() }
async function onImportFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  importPreview.value = { file, name: file.name, size: file.size }
  importProgress.value = { done: 0, total: 0, skipped: 0, errors: 0, running: false, errorMsg: '' }
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
      importProgress.value.errors = 1
      importProgress.value.running = false
      importProgress.value.total = -1
      importProgress.value.errorMsg = text.slice(0, 400)
      return
    }
    importProgress.value.done = 1
    importProgress.value.total = 1
    importProgress.value.running = false
    await load()
  } catch (err) {
    importProgress.value.errors = 1
    importProgress.value.running = false
    importProgress.value.total = -1
    importProgress.value.errorMsg = String(err)
  }
}

// ── Duplicates ──
const duplicatesOpen = ref(false)
const duplicatePairs = ref([])
const duplicatesLoading = ref(false)
const duplicateError = ref('')
const duplicateThreshold = ref('0.92')
const duplicateThresholdNum = computed({
  get: () => Number(duplicateThreshold.value),
  set: v => { duplicateThreshold.value = Number(v).toFixed(2) },
})
const DUP_THRESHOLD_MIN = 0.80
const DUP_THRESHOLD_MAX = 0.98

function normalizeDuplicateThreshold(value) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0.92'
  return Math.min(DUP_THRESHOLD_MAX, Math.max(DUP_THRESHOLD_MIN, n)).toFixed(2)
}

async function openDuplicates() {
  duplicatesOpen.value = true
  try {
    const settings = await apiFetch('/settings').then(r => r.ok ? r.json() : null)
    duplicateThreshold.value = normalizeDuplicateThreshold(settings?.dup_threshold || '0.92')
  } catch {
    duplicateThreshold.value = '0.92'
  }
  await scanDuplicates()
}

async function scanDuplicates() {
  duplicatesLoading.value = true
  duplicateError.value = ''
  duplicatePairs.value = []
  try {
    const params = new URLSearchParams()
    if (selectedProject.value) params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    duplicateThreshold.value = normalizeDuplicateThreshold(duplicateThreshold.value)
    params.set('threshold', duplicateThreshold.value)
    const qs = params.toString()
    const r = await apiFetch(`/duplicates${qs ? '?' + qs : ''}`)
    if (!r.ok) {
      const text = await r.text()
      duplicateError.value = `Scan failed (${r.status}): ${text.slice(0, 180) || r.statusText}`
      return
    }
    duplicatePairs.value = await r.json()
  } catch (err) {
    duplicateError.value = `Scan failed: ${err?.message || err}`
  } finally {
    duplicatesLoading.value = false
  }
}

async function deleteDupMem(id, pairIdx) {
  await apiJSON(`/memories/${id}`, { method: 'DELETE' })
  duplicatePairs.value = duplicatePairs.value.filter(pair => pair.id1 !== id && pair.id2 !== id)
  await load()
}

// ── Conflicts ──
const conflictsOpen = ref(false)
const conflictPairs = ref([])
const conflictsLoading = ref(false)
const conflictError = ref('')
const conflictMinSim = ref('0.50')
const conflictMinSimNum = computed({
  get: () => Number(conflictMinSim.value),
  set: v => { conflictMinSim.value = Number(v).toFixed(2) },
})

async function openConflicts() {
  conflictsOpen.value = true
  await scanConflicts()
}

async function scanConflicts() {
  conflictsLoading.value = true
  conflictError.value = ''
  conflictPairs.value = []
  try {
    const params = new URLSearchParams()
    if (selectedProject.value) params.set('project_slug', selectedProject.value)
    if (selectedType.value) params.set('type', selectedType.value)
    params.set('min_sim', conflictMinSim.value)
    const qs = params.toString()
    const r = await apiFetch(`/conflicts${qs ? '?' + qs : ''}`)
    if (!r.ok) {
      const txt = await r.text()
      conflictError.value = `Scan failed (${r.status}): ${txt.slice(0, 180) || r.statusText}`
      return
    }
    conflictPairs.value = await r.json()
  } catch (err) {
    conflictError.value = `Scan failed: ${err?.message || err}`
  } finally {
    conflictsLoading.value = false
  }
}

async function deleteConflictMem(id) {
  await apiJSON(`/memories/${id}`, { method: 'DELETE' })
  conflictPairs.value = conflictPairs.value.filter(pair => pair.id1 !== id && pair.id2 !== id)
  await load()
}

// ── Display helpers ──
function projectDisplayName(id) {
  return projectMap.value[id] || ''
}

function sourceIconUrl(source) {
  const tone = isDark.value ? 'dark' : 'light'
  return source === 'codex'
    ? `/ui/assets/openai-${tone}.svg`
    : `/ui/assets/claude-${tone}.svg`
}
function sourceLabel(source) {
  return source === 'codex' ? 'Codex' : 'Claude Code'
}

const TYPE_TAG = { feedback: 'success', project: 'info', user: 'default', reference: 'warning' }
function typeTagType(type) { return TYPE_TAG[type] || 'default' }

// De-saturated type palette — kept in sync with the card/detail pills
// (NodeDetailPanel.vue, MemoryDetailModal.vue) so Type reads identically
// everywhere. Light/dark each get a tuned pair.
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

function openDetail(m) { detailTarget.value = m }
function resetFilters() {
  selectedProject.value = ''
  selectedType.value = ''
  searchText.value = ''
  load()
}

const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || null
function fmtDate(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (browserTz) {
    try {
      const parts = new Intl.DateTimeFormat('sv', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZoneName: 'short', hour12: false, timeZone: browserTz,
      }).formatToParts(d)
      const get = tp => parts.find(p => p.type === tp)?.value ?? ''
      const zone = get('timeZoneName')
      return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}${zone ? ' ' + zone : ''}`
    } catch { /* fall through */ }
  }
  return d.toLocaleDateString('sv') + ' ' + d.toLocaleTimeString('en-GB', { hour12: false })
}
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

// ── Data table ──
const columns = computed(() => [
  { type: 'selection' },
  {
    title: '',
    key: 'source',
    width: 44,
    align: 'center',
    render: row => h('img', {
      src: sourceIconUrl(row.source_client),
      title: sourceLabel(row.source_client),
      width: 15, height: 15,
      style: 'display:inline-block;vertical-align:middle',
    }),
  },
  {
    title: t('Project'),
    key: 'project',
    width: 150,
    ellipsis: { tooltip: true },
    render: row => projectDisplayName(row.project_id) || '—',
  },
  {
    title: t('Type'),
    key: 'type',
    width: 110,
    render: row => h('span', { class: 'mem-type-pill', style: typePillStyle(row.type) }, t(row.type)),
  },
  {
    title: t('Name'),
    key: 'name',
    minWidth: 180,
    ellipsis: { tooltip: true },
  },
  {
    title: t('Description'),
    key: 'description',
    minWidth: 260,
    ellipsis: { tooltip: true },
  },
  {
    title: t('Hits'),
    key: 'hit_count',
    width: 80,
    sorter: (a, b) => (a.hit_count || 0) - (b.hit_count || 0),
    render: row => row.hit_count > 0 ? row.hit_count : '—',
  },
  {
    title: t('Updated'),
    key: 'updated_at',
    width: 110,
    sorter: (a, b) => new Date(a.updated_at) - new Date(b.updated_at),
    defaultSortOrder: 'descend',
    render: row => h('span', { title: fmtDate(row.updated_at) }, relTime(row.updated_at)),
  },
  {
    title: '',
    key: 'actions',
    width: 120,
    render: row => h('div', { class: 'mp-actions' }, [
      h(NSpace, { size: 4, wrap: false, justify: 'end' }, () => [
      h(NButton, { size: 'tiny', quaternary: true, title: t('Edit'), onClick: e => { e.stopPropagation(); openEdit(row) } }, { icon: () => h(NIcon, null, { default: () => h(IconEdit) }) }),
      h(NButton, { size: 'tiny', quaternary: true, title: t('Clone'), onClick: e => { e.stopPropagation(); openClone(row) } }, { icon: () => h(NIcon, null, { default: () => h(IconClone) }) }),
      h(NButton, { size: 'tiny', quaternary: true, type: 'error', title: t('Delete'), onClick: e => { e.stopPropagation(); del(row) } }, { icon: () => h(NIcon, null, { default: () => h(IconTrash) }) }),
      ]),
    ]),
  },
])

function rowProps(row) {
  return {
    style: 'cursor:pointer',
    onClick: e => {
      if (e.target.closest('button') || e.target.closest('.n-checkbox')) return
      openDetail(row)
    },
  }
}

const pagination = reactive({
  page: 1,
  pageSize: 20,
  showSizePicker: true,
  pageSizes: [20, 50, 100],
  onChange: p => { pagination.page = p },
  onUpdatePageSize: ps => { pagination.pageSize = ps; pagination.page = 1 },
})
watch(filtered, () => { pagination.page = 1 })

onMounted(async () => {
  document.addEventListener('keydown', e => {
    if (e.key === 'n' && !e.ctrlKey && !e.metaKey && !e.altKey &&
        !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName)) {
      e.preventDefault()
      openWrite()
    }
  })
  const projRes = await apiFetch('/projects')
  if (projRes.status === 401) {
    loginOpen.value = true
    return
  }
  projects.value = await projRes.json()
  autoSelectProject()
  await load()
})
</script>

<style scoped>
.table-wrap :deep(.mp-actions) {
  opacity: 0;
  transition: opacity 0.12s ease;
}
.table-wrap :deep(.n-data-table-tr:hover .mp-actions) {
  opacity: 1;
}
.table-wrap :deep(.n-data-table-td--selection .n-checkbox) {
  opacity: 0;
  transition: opacity 0.12s ease;
}
.table-wrap :deep(.n-data-table-tr:hover .n-data-table-td--selection .n-checkbox),
.table-wrap :deep(.n-data-table-td--selection .n-checkbox.n-checkbox--checked),
.table-wrap :deep(.n-data-table-td--selection .n-checkbox.n-checkbox--indeterminate) {
  opacity: 1;
}
.table-wrap :deep(.n-data-table-th--selection .n-checkbox) {
  opacity: 0;
  transition: opacity 0.12s ease;
}
.table-wrap :deep(.n-data-table-thead:hover .n-data-table-th--selection .n-checkbox),
.table-wrap :deep(.n-data-table-th--selection .n-checkbox.n-checkbox--checked),
.table-wrap :deep(.n-data-table-th--selection .n-checkbox.n-checkbox--indeterminate) {
  opacity: 1;
}
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
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1 1 auto;
  min-width: 0;
}
.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}
.table-wrap {
  flex: 1;
  min-height: 0;
}
.bulk-bar {
  position: fixed;
  left: 50%;
  bottom: 24px;
  transform: translateX(-50%);
  z-index: 100;
  width: auto;
}
.bulk-enter-active,
.bulk-leave-active { transition: opacity 0.2s, transform 0.2s; }
.bulk-enter-from,
.bulk-leave-to { opacity: 0; transform: translate(-50%, 12px); }

.login-logo { display: flex; align-items: center; gap: 10px; margin-bottom: 6px; }
.login-title { font-size: 16px; font-weight: 700; }
.login-subtitle { font-size: 12px; opacity: 0.7; margin-bottom: 14px; }

.dup-list { display: flex; flex-direction: column; gap: 10px; }
.dup-pair :deep(.n-card__content) {
  display: grid;
  grid-template-columns: 1fr 80px 1fr;
  gap: 12px;
  align-items: start;
}
.dup-side { min-width: 0; }
.dup-side :deep(.n-text) { word-break: break-word; }
.dup-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  justify-content: center;
}
</style>
