<!-- frontend/src/SkeletonPage.vue -->
<template>
  <div class="sk-app" :style="cssVars">
    <!-- Login overlay -->
    <BaseModal :show="loginOpen">
      <n-card v-if="loginOpen" title="Memory Orchestrator" style="width:340px" :bordered="false">
        <n-space vertical :size="12">
          <n-input v-model:value="loginInput" type="password" show-password-on="click"
            :placeholder="t('Admin token…')" @keydown.enter="submitLogin" />
          <n-text v-if="loginError" type="error" style="font-size:12px">{{ loginError }}</n-text>
          <n-button type="primary" block :loading="loginLoading" @click="submitLogin">{{ t('Sign in') }}</n-button>
          <n-button text size="small" @click="skipLogin">{{ t('Continue without token') }}</n-button>
        </n-space>
      </n-card>
    </BaseModal>

    <template v-if="!loginOpen">
      <AppHeader
        :loginOpen="loginOpen"
        @logout="logout"
      />

      <div class="sk-body">
        <!-- Column 1: Icon strip -->
        <ProjectIconStrip
          :projects="projects"
          :activeId="selectedProject?.id"
          @select="selectProject"
          @create="openNewProjectModal"
          @context-menu="openProjectContextMenu"
        />

        <!-- Column 2: Tree panel -->
        <SkeletonTreePanel
          v-if="selectedProject"
          :nodes="skeletonTree"
          :selectedId="selectedNode?.id"
          :projName="selectedProject.display_name || selectedProject.slug"
          :memoryCountMap="memoryCountMap"
          @select="selectNode"
          @patch="onPatch"
          @delete="onDelete"
          @context-menu="openContextMenu"
          @reorder="onReorder"
          @add-root="onAddRoot"
        />
        <n-empty v-else class="tree-empty" :description="t('Select or create project')" />

        <!-- Column 3: Detail panel -->
        <NodeDetailPanel
          :node="selectedNode"
          :memories="nodeMemories"
          :all-tags="allTags"
          @save-hint="onSaveHint"
          @update-tags="onUpdateTags"
          @add-memory="addMemoryOpen = true"
          @unlink-memory="unlinkMemory"
          @open-detail="m => detailMemory = m"
          @edit-memory="openEditMemory"
          @edit-node="openEditNode"
        />
      </div>
    </template>

    <!-- Context menu -->
    <ContextMenu
      :visible="ctxVisible"
      :x="ctxX"
      :y="ctxY"
      :depth="ctxDepth"
      :is-builtin="ctxNode?.is_builtin ?? false"
      @add-child="onAddChild"
      @delete="onDeleteNode"
    />

    <!-- Project context menu -->
    <n-dropdown
      trigger="manual"
      placement="bottom-start"
      :show="projCtxVisible"
      :x="projCtxX"
      :y="projCtxY"
      :options="projCtxOptions"
      @select="onProjectCtxSelect"
      @clickoutside="closeProjectContextMenu"
    />

    <!-- Memory detail modal -->
    <MemoryDetailModal :memory="detailMemory" @close="detailMemory = null" @edit="openEditMemory" />

    <!-- New project modal -->
    <BaseModal :show="newProjectOpen" :mask-closable="true" @close="newProjectOpen = false">
      <n-card v-if="newProjectOpen" :title="t('New Project')" closable style="width:380px" :bordered="false" @close="newProjectOpen = false">
        <n-space vertical :size="12">
          <n-input v-model:value="newProjectName" :placeholder="t('Project name…')"
            @keydown.enter="createProject" ref="newProjectInput" />
          <n-button type="primary" block :disabled="!newProjectName" :loading="isCreatingProject" @click="createProject">
            {{ t('Create') }}
          </n-button>
        </n-space>
      </n-card>
    </BaseModal>

    <!-- Edit project modal -->
    <BaseModal :show="editProjectOpen" :mask-closable="true" @close="editProjectOpen = false">
      <n-card v-if="editProjectOpen" :title="t('Edit project')" closable style="width:380px" :bordered="false" @close="editProjectOpen = false">
        <n-space vertical :size="12">
          <n-input v-model:value="editProjectName" :placeholder="t('Project name…')"
            @keydown.enter="submitEditProject" ref="editProjectInput" />
          <n-button type="primary" block :disabled="!editProjectName.trim()" :loading="isEditingProject" @click="submitEditProject">
            {{ t('Save') }}
          </n-button>
        </n-space>
      </n-card>
    </BaseModal>

    <!-- Delete project confirm modal -->
    <BaseModal :show="!!deleteProjectTarget" :mask-closable="true" @close="deleteProjectTarget = null">
      <n-card v-if="deleteProjectTarget" :title="t('Delete project')" closable style="width:420px" :bordered="false" @close="deleteProjectTarget = null">
        <n-text strong style="display:block">{{ deleteProjectTarget.display_name || deleteProjectTarget.slug }}</n-text>
        <n-text depth="3" tag="p" style="margin-top:8px;font-size:12px">
          {{ t('Delete project "{name}" and all its memories and skeleton nodes? This cannot be undone.', { name: deleteProjectTarget.display_name || deleteProjectTarget.slug }) }}
        </n-text>
        <template #footer>
          <n-space justify="end">
            <n-button @click="deleteProjectTarget = null">{{ t('Cancel') }}</n-button>
            <n-button type="error" :loading="isDeletingProject" @click="confirmDeleteProject">{{ t('Delete') }}</n-button>
          </n-space>
        </template>
      </n-card>
    </BaseModal>

    <!-- Delete node confirm modal -->
    <BaseModal :show="!!deleteNodeTarget" :mask-closable="true" @close="deleteNodeTarget = null">
      <n-card v-if="deleteNodeTarget" :title="t('Delete node')" closable style="width:420px" :bordered="false" @close="deleteNodeTarget = null">
        <n-text depth="3" tag="p" style="font-size:12px">
          {{ t('Delete this node and unlink its memories?') }}
        </n-text>
        <template #footer>
          <n-space justify="end">
            <n-button @click="deleteNodeTarget = null">{{ t('Cancel') }}</n-button>
            <n-button type="error" :loading="isDeletingNode" @click="confirmDeleteNode">{{ t('Delete') }}</n-button>
          </n-space>
        </template>
      </n-card>
    </BaseModal>

    <!-- Node name modal (add top-level / add child / rename) -->
    <BaseModal :show="nodeModalOpen" :mask-closable="true" @close="nodeModalOpen = false">
      <n-card v-if="nodeModalOpen" :title="nodeModalTitle" closable style="width:460px" :bordered="false" @close="nodeModalOpen = false">
        <n-space vertical :size="12">
          <n-form-item :label="t('Name')" label-placement="top" :show-feedback="false">
            <n-input
              v-model:value="nodeModalName"
              :disabled="nodeModalMode === 'rename' && !!nodeModalNode?.is_builtin"
              :placeholder="t('Node name…')"
              @keydown.enter="submitNodeModal"
              ref="nodeModalInput"
            />
          </n-form-item>
          <n-form-item :label="t('Tags')" label-placement="top" :show-feedback="false">
            <TagPicker v-model="nodeModalTags" :all-tags="allTags" />
          </n-form-item>
          <n-form-item :label="t('Description')" label-placement="top" :show-feedback="false">
            <n-input
              v-model:value="nodeModalDescription"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 4 }"
              :placeholder="t('One-line summary…')"
            />
          </n-form-item>
          <n-form-item :label="t('Prompt Hint')" label-placement="top" :show-feedback="false">
            <n-input
              v-model:value="nodeModalPromptHint"
              type="textarea"
              :autosize="{ minRows: 2, maxRows: 5 }"
              :placeholder="t('Prompt hint…')"
            />
          </n-form-item>
          <n-button type="primary" block :disabled="!nodeModalName.trim()" :loading="nodeModalSaving" @click="submitNodeModal">
            {{ nodeModalMode === 'rename' ? t('Save') : t('Create') }}
          </n-button>
        </n-space>
      </n-card>
    </BaseModal>

    <!-- Add memory modal -->
    <BaseModal :show="addMemoryOpen" :mask-closable="true" @close="addMemoryOpen = false">
      <n-card v-if="addMemoryOpen" closable style="width:520px" :bordered="false"
        :title="t('Add memory → {name}', { name: selectedNode?.name })"
        @close="addMemoryOpen = false">
        <n-tabs v-model:value="addMemoryTab" type="line" animated>
          <n-tab-pane name="write" :tab="t('Write new')">
            <n-space vertical :size="12">
              <n-text v-if="selectedNode?.prompt_hint" depth="3" italic style="font-size:11px">{{ selectedNode.prompt_hint }}</n-text>
              <n-radio-group v-model:value="memForm.type" size="small">
                <n-radio-button v-for="tp in ['user','feedback','project','reference']" :key="tp" :value="tp">{{ t(tp) }}</n-radio-button>
              </n-radio-group>
              <n-form-item :label="t('Name')" label-placement="top" :show-feedback="false">
                <n-input v-model:value="memForm.name" :placeholder="t('Short identifier…')" />
              </n-form-item>
              <n-form-item :label="t('Description')" label-placement="top" :show-feedback="false">
                <n-input v-model:value="memForm.description" :placeholder="t('One-line summary…')" />
              </n-form-item>
              <n-form-item :label="t('Content')" label-placement="top" :show-feedback="false">
                <MarkdownEditor v-model:value="memForm.content" min-height="160px" class="add-mem-editor" />
              </n-form-item>
              <n-text v-if="memError" type="error" style="font-size:12px">{{ memError }}</n-text>
              <n-space justify="end">
                <n-button @click="addMemoryOpen = false">{{ t('Cancel') }}</n-button>
                <n-button type="primary" :loading="isMemSaving" :disabled="!memForm.name || !memForm.content" @click="submitAddMemory">{{ t('Write') }}</n-button>
              </n-space>
            </n-space>
          </n-tab-pane>

          <n-tab-pane name="select" :tab="t('Select existing')">
            <n-space vertical :size="12">
              <n-input v-model:value="selectMemQuery" :placeholder="t('Search memories…')" clearable @input="onSelectMemSearch" />
              <n-spin :show="selectMemLoading">
                <n-empty v-if="selectMemResults.length === 0" :description="selectMemQuery ? t('No memories found') : t('Search to find existing memories')" style="padding:16px 0" />
                <div v-else class="select-mem-list">
                  <n-card v-for="m in selectMemResults" :key="m.id" size="small" hoverable
                    :class="['select-mem-item', { chosen: selectMemChosen?.id === m.id }]"
                    @click="selectMemChosen = m">
                    <n-space align="center" :size="8" :wrap="false">
                      <n-tag size="tiny" :type="typeTagType(m.type)" :bordered="false">{{ t(m.type) }}</n-tag>
                      <n-text strong style="font-size:12px;white-space:nowrap">{{ m.name }}</n-text>
                      <n-text depth="3" style="font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ m.description }}</n-text>
                    </n-space>
                  </n-card>
                </div>
              </n-spin>
              <n-text v-if="memError" type="error" style="font-size:12px">{{ memError }}</n-text>
              <n-space justify="end">
                <n-button @click="addMemoryOpen = false">{{ t('Cancel') }}</n-button>
                <n-button type="primary" :loading="isMemSaving" :disabled="!selectMemChosen" @click="submitLinkMemory">{{ t('Link') }}</n-button>
              </n-space>
            </n-space>
          </n-tab-pane>
        </n-tabs>
      </n-card>
    </BaseModal>

    <!-- Edit memory modal (shared component) -->
    <MemoryEditModal
      :show="editModalShow"
      :memory="editModalMemory"
      @close="editModalShow = false"
      @saved="onEditSaved"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick, provide, h } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { apiFetch, apiJSON, errText } from './api.js'
import { useAppStore } from './stores/app.js'
import AppHeader from './AppHeader.vue'
import BaseModal from './BaseModal.vue'
import MemoryEditModal from './MemoryEditModal.vue'
import {
  NCard, NInput, NButton, NSpace, NText, NTabs, NTabPane,
  NRadioGroup, NRadioButton, NFormItem, NSpin, NTag, NEmpty, NIcon, NDropdown, useThemeVars,
  useMessage,
} from 'naive-ui'
import ProjectIconStrip from './ProjectIconStrip.vue'
import SkeletonTreePanel from './SkeletonTreePanel.vue'
import NodeDetailPanel from './NodeDetailPanel.vue'
import ContextMenu from './ContextMenu.vue'
import { IconTrash, IconEdit } from './icons.js'
import MemoryDetailModal from './MemoryDetailModal.vue'
import TagPicker from './TagPicker.vue'
import MarkdownEditor from './MarkdownEditor.vue'

const router = useRouter()
const appStore = useAppStore()
const { isDark, lang, loginOpen, loginInput, loginError, loginLoading } = storeToRefs(appStore)
const { t, toggleTheme, toggleLang } = appStore
provide('t', t)

const message = useMessage()

const vars = useThemeVars()
const cssVars = computed(() => ({
  '--app-bg': vars.value.bodyColor,
  '--border': vars.value.borderColor,
  '--accent': vars.value.primaryColor,
}))

const TYPE_TAG = { feedback: 'success', project: 'info', user: 'default', reference: 'warning' }
function typeTagType(type) { return TYPE_TAG[type] || 'default' }

// ── Auth (delegates to store) ─────────────────────────────────────────────────
async function submitLogin() {
  const ok = await appStore.submitLogin()
  if (ok) await loadProjects()
}

async function skipLogin() {
  const ok = await appStore.skipLogin()
  if (ok) await loadProjects()
}

async function logout() {
  await appStore.logout()
}

const detailMemory = ref(null)

// ── Projects ──────────────────────────────────────────────────────────────────
const LS_PROJECT_KEY = 'mo_selected_project'
const projects = ref([])
const selectedProject = ref(null)
watch(selectedProject, p => { if (p) localStorage.setItem(LS_PROJECT_KEY, p.slug) })

async function loadProjects() {
  try {
    const r = await apiFetch('/projects')
    if (r.status === 401) { loginOpen.value = true; return }
    projects.value = await r.json()
  } catch { loginOpen.value = true }
}

async function selectProject(p) {
  selectedProject.value = p
  selectedNode.value = null
  nodeMemories.value = []
  await loadSkeleton(p.id)
  // Auto-select the first node so the detail panel isn't empty
  const first = flatNodes.value[0]
  if (first) await selectNode(first)
}

const newProjectOpen = ref(false)
const newProjectName = ref('')
const isCreatingProject = ref(false)
const newProjectInput = ref(null)

function openNewProjectModal() {
  newProjectName.value = ''
  newProjectOpen.value = true
  nextTick(() => newProjectInput.value?.focus())
}

async function createProject() {
  if (!newProjectName.value) return
  isCreatingProject.value = true
  try {
    const slug = newProjectName.value.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '')
    const p = await apiJSON('/projects', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, display_name: newProjectName.value }),
    })
    newProjectOpen.value = false
    await loadProjects()
    await selectProject(p)
  } finally { isCreatingProject.value = false }
}

// ── Project context menu / delete ──────────────────────────────────────────────
const projCtxVisible = ref(false)
const projCtxX = ref(0)
const projCtxY = ref(0)
const projCtxProject = ref(null)
function renderMenuIcon(icon) {
  return () => h(NIcon, null, { default: () => h(icon) })
}
const projCtxOptions = computed(() => [
  { label: t('Edit project'), key: 'edit', icon: renderMenuIcon(IconEdit) },
  { label: t('Delete project'), key: 'delete', icon: renderMenuIcon(IconTrash) },
])

function openProjectContextMenu({ x, y, project }) {
  projCtxX.value = x; projCtxY.value = y; projCtxProject.value = project
  projCtxVisible.value = true
}
function closeProjectContextMenu() { projCtxVisible.value = false; projCtxProject.value = null }

function onProjectCtxSelect(key) {
  const project = projCtxProject.value
  closeProjectContextMenu()
  if (key === 'edit' && project) openEditProject(project)
  else if (key === 'delete' && project) requestDeleteProject(project)
}

// ── Edit project (rename display_name) ─────────────────────────────────────────
const editProjectOpen = ref(false)
const editProjectName = ref('')
const editProjectTarget = ref(null)
const isEditingProject = ref(false)
const editProjectInput = ref(null)

function openEditProject(project) {
  editProjectTarget.value = project
  editProjectName.value = project.display_name || project.slug || ''
  editProjectOpen.value = true
  nextTick(() => editProjectInput.value?.focus())
}

async function submitEditProject() {
  const project = editProjectTarget.value
  const name = editProjectName.value.trim()
  if (!project || !name) return
  isEditingProject.value = true
  try {
    await apiJSON(`/projects/${project.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ display_name: name }),
    })
    editProjectOpen.value = false
    if (selectedProject.value?.id === project.id) selectedProject.value.display_name = name
    await loadProjects()
    message.success(t('Project updated'))
  } finally { isEditingProject.value = false }
}

// ── Delete project (confirm modal) ─────────────────────────────────────────────
const deleteProjectTarget = ref(null)
const isDeletingProject = ref(false)

function requestDeleteProject(project) {
  deleteProjectTarget.value = project
}

async function confirmDeleteProject() {
  const project = deleteProjectTarget.value
  if (!project) return
  isDeletingProject.value = true
  try {
    await apiJSON(`/projects/${project.id}`, { method: 'DELETE' })
    message.success(t('Project deleted'))
    if (selectedProject.value?.id === project.id) {
      selectedProject.value = null
      selectedNode.value = null
      nodeMemories.value = []
    }
    await loadProjects()
    if (!selectedProject.value && projects.value.length) await selectProject(projects.value[0])
    deleteProjectTarget.value = null
  } finally { isDeletingProject.value = false }
}

// ── Skeleton tree ─────────────────────────────────────────────────────────────
const skeletonTree = ref([])
const selectedNode = ref(null)
const nodeMemories = ref([])

function flattenTree(nodes, acc = []) {
  for (const n of nodes) { acc.push(n); if (n.children?.length) flattenTree(n.children, acc) }
  return acc
}
const flatNodes = computed(() => flattenTree(skeletonTree.value))
const allTags = computed(() => [...new Set(flatNodes.value.flatMap(n => n.tags || []))].sort())

const memoryCountMap = ref({})

async function loadSkeleton(projectId) {
  skeletonTree.value = await apiJSON(`/projects/${projectId}/skeleton`)
}

async function selectNode(node) {
  selectedNode.value = node
  nodeMemories.value = await apiJSON(`/skeleton-nodes/${node.id}/memories`)
  memoryCountMap.value = { ...memoryCountMap.value, [node.id]: nodeMemories.value.length }
}

// ── Patch / delete ────────────────────────────────────────────────────────────
async function onPatch({ id, patch }) {
  await apiFetch(`/skeleton-nodes/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  await loadSkeleton(selectedProject.value.id)
  if (selectedNode.value?.id === id) {
    const updated = flatNodes.value.find(n => n.id === id)
    if (updated) selectedNode.value = updated
  }
}

// ── Delete node (confirm modal) ────────────────────────────────────────────────
const deleteNodeTarget = ref(null)
const isDeletingNode = ref(false)

function onDelete(nodeId) {
  deleteNodeTarget.value = nodeId
}

async function confirmDeleteNode() {
  const nodeId = deleteNodeTarget.value
  if (!nodeId) return
  isDeletingNode.value = true
  try {
    const r = await apiFetch(`/skeleton-nodes/${nodeId}`, { method: 'DELETE' })
    if (r.status === 409) { message.warning(t('Built-in nodes cannot be deleted.')); return }
    if (selectedNode.value?.id === nodeId) { selectedNode.value = null; nodeMemories.value = [] }
    await loadSkeleton(selectedProject.value.id)
    deleteNodeTarget.value = null
  } catch (e) { message.error(e.message) }
  finally { isDeletingNode.value = false }
}

async function onSaveHint(hint) {
  await onPatch({ id: selectedNode.value.id, patch: { prompt_hint: hint } })
}

async function onUpdateTags(tags) {
  await onPatch({ id: selectedNode.value.id, patch: { tags } })
  if (selectedNode.value) selectedNode.value = { ...selectedNode.value, tags }
}

async function onReorder(orderedIds) {
  await apiFetch('/skeleton-nodes/reorder', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: selectedProject.value.id, ordered_ids: orderedIds }),
  })
  await loadSkeleton(selectedProject.value.id)
}

async function unlinkMemory(memoryId) {
  await apiFetch(`/skeleton-nodes/${selectedNode.value.id}/memories/${memoryId}`, { method: 'DELETE' })
  nodeMemories.value = nodeMemories.value.filter(m => m.id !== memoryId)
  memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
}

// ── Context menu ──────────────────────────────────────────────────────────────
const ctxVisible = ref(false)
const ctxX = ref(0)
const ctxY = ref(0)
const ctxDepth = ref(0)
const ctxNode = ref(null)

function openContextMenu({ x, y, node, depth }) {
  ctxX.value = x; ctxY.value = y; ctxDepth.value = depth; ctxNode.value = node
  ctxVisible.value = true
}

function closeContextMenu() { ctxVisible.value = false; ctxNode.value = null }

onMounted(() => {
  document.addEventListener('click', closeContextMenu)
})

function onAddChild() {
  const node = ctxNode.value
  closeContextMenu()
  if (!node) return
  openNodeModal({ mode: 'add-child', parentId: node.id })
}

function onAddRoot() {
  if (!selectedProject.value) return
  openNodeModal({ mode: 'add-root', parentId: null })
}

function openEditNode(node) {
  if (!node) return
  openNodeModal({ mode: 'rename', node })
}

// ── Node name modal (add top-level / add child / rename) ──────────────────────
const nodeModalOpen = ref(false)
const nodeModalMode = ref('add-root')   // 'add-root' | 'add-child' | 'rename'
const nodeModalName = ref('')
const nodeModalDescription = ref('')
const nodeModalPromptHint = ref('')
const nodeModalTags = ref([])
const nodeModalParentId = ref(null)
const nodeModalNode = ref(null)
const nodeModalSaving = ref(false)
const nodeModalInput = ref(null)

const nodeModalTitle = computed(() => ({
  'add-root': t('New top-level node'),
  'add-child': t('New child node'),
  'rename': t('Rename node'),
}[nodeModalMode.value]))

function openNodeModal({ mode, parentId = null, node = null }) {
  nodeModalMode.value = mode
  nodeModalParentId.value = parentId
  nodeModalNode.value = node
  nodeModalName.value = mode === 'rename' ? (node?.name ?? '') : ''
  nodeModalDescription.value = mode === 'rename' ? (node?.description ?? '') : ''
  nodeModalPromptHint.value = mode === 'rename' ? (node?.prompt_hint ?? '') : ''
  nodeModalTags.value = mode === 'rename' ? [...(node?.tags || [])] : []
  nodeModalOpen.value = true
  nextTick(() => nodeModalInput.value?.focus())
}

async function submitNodeModal() {
  const name = nodeModalName.value.trim()
  if (!name) return
  nodeModalSaving.value = true
  try {
    if (nodeModalMode.value === 'rename') {
      await onPatch({
        id: nodeModalNode.value.id,
        patch: {
          name,
          description: nodeModalDescription.value,
          prompt_hint: nodeModalPromptHint.value,
          tags: nodeModalTags.value,
        },
      })
    } else {
      await apiJSON('/skeleton-nodes', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          project_id: selectedProject.value.id,
          parent_id: nodeModalParentId.value,
          name,
          description: nodeModalDescription.value,
          prompt_hint: nodeModalPromptHint.value,
          tags: nodeModalTags.value,
        }),
      })
      await loadSkeleton(selectedProject.value.id)
    }
    nodeModalOpen.value = false
  } finally {
    nodeModalSaving.value = false
  }
}

async function onDeleteNode() {
  const node = ctxNode.value
  closeContextMenu()
  if (node) await onDelete(node.id)
}

// ── Edit memory (shared modal) ───────────────────────────────────────────────
const editModalShow = ref(false)
const editModalMemory = ref(null)

async function openEditMemory(m) {
  detailMemory.value = null
  // The node-memories list omits heavy fields (content); fetch the full record
  // so the edit form echoes the existing content instead of opening blank.
  let full = m
  if (m && m.content === undefined) {
    try { full = { ...m, ...(await apiJSON(`/memories/${m.id}`)) } } catch { full = m }
  }
  editModalMemory.value = full
  editModalShow.value = true
}

async function onEditSaved() {
  editModalShow.value = false
  if (selectedNode.value) {
    nodeMemories.value = await apiJSON(`/skeleton-nodes/${selectedNode.value.id}/memories`)
    memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
  }
}

// ── Add memory ────────────────────────────────────────────────────────────────
const addMemoryOpen = ref(false)
const addMemoryTab = ref('write')
const isMemSaving = ref(false)
const memError = ref('')
const memForm = ref({ type: 'project', name: '', description: '', content: '' })

// Select-existing state
const selectMemQuery = ref('')
const selectMemResults = ref([])
const selectMemChosen = ref(null)
const selectMemLoading = ref(false)
let _selectSearchTimer = null

function onSelectMemSearch() {
  selectMemChosen.value = null
  clearTimeout(_selectSearchTimer)
  if (!selectMemQuery.value.trim()) { selectMemResults.value = []; return }
  _selectSearchTimer = setTimeout(async () => {
    selectMemLoading.value = true
    try {
      const slug = selectedProject.value?.slug
      const q = encodeURIComponent(selectMemQuery.value)
      selectMemResults.value = await apiJSON(`/memories?project_slug=${slug}&q=${q}&limit=30`)
    } catch { selectMemResults.value = [] }
    finally { selectMemLoading.value = false }
  }, 300)
}

watch(addMemoryOpen, open => {
  if (!open) {
    addMemoryTab.value = 'write'
    selectMemQuery.value = ''
    selectMemResults.value = []
    selectMemChosen.value = null
    memError.value = ''
    memForm.value = { type: 'project', name: '', description: '', content: '' }
  }
})

async function submitAddMemory() {
  if (!memForm.value.name || !memForm.value.content) return
  isMemSaving.value = true; memError.value = ''
  try {
    const mem = await apiJSON('/memories', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...memForm.value, project_id: selectedProject.value.id }),
      skipErrorToast: true,
    })
    await apiJSON(`/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: mem.id }),
      skipErrorToast: true,
    })
    addMemoryOpen.value = false
    if (selectedNode.value) {
      nodeMemories.value = await apiJSON(`/skeleton-nodes/${selectedNode.value.id}/memories`)
      memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
    }
  } catch (e) { memError.value = errText(e) }
  finally { isMemSaving.value = false }
}

async function submitLinkMemory() {
  if (!selectMemChosen.value) return
  isMemSaving.value = true; memError.value = ''
  try {
    await apiJSON(`/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: selectMemChosen.value.id }),
      skipErrorToast: true,
    })
    addMemoryOpen.value = false
    nodeMemories.value = await apiJSON(`/skeleton-nodes/${selectedNode.value.id}/memories`)
    memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
  } catch (e) { memError.value = errText(e) }
  finally { isMemSaving.value = false }
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  const r = await apiFetch('/projects')
  if (r.status === 401) { loginOpen.value = true; return }
  projects.value = await r.json()
  if (projects.value.length > 0) {
    const saved = localStorage.getItem(LS_PROJECT_KEY)
    const match = saved && projects.value.find(p => p.slug === saved)
    await selectProject(match || projects.value[0])
  }
})
</script>

<style scoped>
.add-mem-editor {
  border: 1px solid var(--n-border-color, #e0e0e6);
  border-radius: 6px;
  overflow: hidden;
}
.add-mem-editor :deep(.cm-editor) { max-height: 240px; }
.sk-app {
  width: 100%;
  max-width: 1600px;
  margin: 0 auto;
  padding: 8px 16px 12px;
  height: 100vh;
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--app-bg);
  box-sizing: border-box;
  text-align: left;
}
.sk-body {
  display: flex;
  flex: 1;
  min-height: 0;
  overflow: hidden;
  border: 1px solid var(--border);
  border-radius: 3px;
}
.tree-empty { width: 220px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; border-right: 1px solid var(--border); }
.select-mem-list { display: flex; flex-direction: column; gap: 6px; max-height: 300px; overflow-y: auto; }
.select-mem-item { cursor: pointer; }
.select-mem-item.chosen { outline: 1.5px solid var(--accent); }
</style>
