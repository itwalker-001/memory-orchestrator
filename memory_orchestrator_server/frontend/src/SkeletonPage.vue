<!-- frontend/src/SkeletonPage.vue -->
<template>
  <div class="sk-app" :class="{ dark: isDark }">
    <!-- Login overlay -->
    <div v-if="loginOpen" class="modal-overlay login-overlay">
      <div class="login-modal">
        <div class="login-title">Memory Orchestrator</div>
        <input v-model="loginInput" class="login-input" type="password"
          placeholder="Admin token…" @keydown.enter="submitLogin" />
        <p v-if="loginError" class="login-error">{{ loginError }}</p>
        <button class="btn-login" :disabled="loginLoading" @click="submitLogin">
          {{ loginLoading ? 'Signing in…' : 'Sign in' }}
        </button>
        <button class="btn-skip" @click="skipLogin">Continue without token</button>
      </div>
    </div>

    <template v-if="!loginOpen">
      <AppHeader
        :loginOpen="loginOpen"
        @open-settings="router.push('/settings')"
        @logout="logout"
      >
        <template #nav>
          <router-link to="/memories">→ Memories</router-link>
        </template>
      </AppHeader>

      <div class="sk-body">
        <!-- Column 1: Icon strip -->
        <ProjectIconStrip
          :projects="projects"
          :activeId="selectedProject?.id"
          @select="selectProject"
          @create="openNewProjectModal"
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
        />
        <div v-else class="tree-empty">{{ t('Select or create project') }}</div>

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
        />
      </div>
    </template>

    <!-- Context menu -->
    <ContextMenu
      :visible="ctxVisible"
      :x="ctxX"
      :y="ctxY"
      :depth="ctxDepth"
      @add-child="onAddChild"
      @rename="onRenameNode"
      @manage-tags="focusTags"
      @delete="onDeleteNode"
    />

    <!-- Memory detail modal -->
    <MemoryDetailModal :memory="detailMemory" @close="detailMemory = null" @edit="detailMemory = null" />

    <!-- New project modal -->
    <div v-if="newProjectOpen" class="modal-overlay" @click.self="newProjectOpen = false">
      <div class="modal" style="max-width:380px">
        <div class="modal-header">
          <span class="modal-title">{{ t('New Project') }}</span>
          <button class="modal-close" @click="newProjectOpen = false"><IconClose width="12" height="12" /></button>
        </div>
        <div style="padding:16px;display:flex;flex-direction:column;gap:10px">
          <input class="sk-input" v-model="newProjectName" :placeholder="t('Project name…')"
            @keydown.enter="createProject" ref="newProjectInput" />
          <button class="btn-save" :disabled="!newProjectName || isCreatingProject" @click="createProject">
            {{ isCreatingProject ? t('Creating…') : t('Create') }}
          </button>
        </div>
      </div>
    </div>

    <!-- Add memory modal -->
    <div v-if="addMemoryOpen" class="modal-overlay" @click.self="addMemoryOpen = false">
      <div class="write-modal">
        <div class="write-header">
          <span class="write-title">{{ t('Add memory → {name}', { name: selectedNode?.name }) }}</span>
          <button class="modal-close" @click="addMemoryOpen = false"><IconClose width="12" height="12" /></button>
        </div>

        <!-- Tab strip -->
        <div class="modal-tabs">
          <button :class="['modal-tab', addMemoryTab === 'write' ? 'active' : '']" @click="addMemoryTab = 'write'">
            {{ t('Write new') }}
          </button>
          <button :class="['modal-tab', addMemoryTab === 'select' ? 'active' : '']" @click="addMemoryTab = 'select'">
            {{ t('Select existing') }}
          </button>
        </div>

        <!-- Write new tab -->
        <template v-if="addMemoryTab === 'write'">
          <div class="write-body">
            <p v-if="selectedNode?.prompt_hint" class="sk-prompt-hint-text">{{ selectedNode.prompt_hint }}</p>
            <div class="write-type-tabs">
              <button v-for="tp in ['user','feedback','project','reference']" :key="tp"
                :class="['type-tab', 'type-tab-'+tp, memForm.type === tp ? 'active' : '']"
                @click="memForm.type = tp">{{ tp }}</button>
            </div>
            <div class="write-section">
              <label class="write-field-label">{{ t('Name') }}</label>
              <input class="write-input" v-model="memForm.name" :placeholder="t('Short identifier…')" />
            </div>
            <div class="write-section">
              <label class="write-field-label">{{ t('Description') }}</label>
              <input class="write-input" v-model="memForm.description" :placeholder="t('One-line summary…')" />
            </div>
            <div class="write-section write-section-grow">
              <label class="write-field-label">{{ t('Content') }}</label>
              <textarea class="write-input write-textarea" v-model="memForm.content" rows="5" />
            </div>
            <p v-if="memError" class="save-hint err">{{ memError }}</p>
          </div>
          <div class="write-footer">
            <button class="btn-cancel" @click="addMemoryOpen = false">{{ t('Cancel') }}</button>
            <button class="btn-save" :disabled="isMemSaving || !memForm.name || !memForm.content" @click="submitAddMemory">
              {{ isMemSaving ? t('Saving…') : t('Write') }}
            </button>
          </div>
        </template>

        <!-- Select existing tab -->
        <template v-else>
          <div class="write-body">
            <input class="write-input" v-model="selectMemQuery"
              :placeholder="t('Search memories…')"
              @input="onSelectMemSearch" />
            <div v-if="selectMemLoading" class="select-mem-hint">{{ t('Loading…') }}</div>
            <div v-else-if="selectMemResults.length === 0 && selectMemQuery" class="select-mem-hint">
              {{ t('No memories found') }}
            </div>
            <div v-else-if="selectMemResults.length === 0" class="select-mem-hint">
              {{ t('Search to find existing memories') }}
            </div>
            <ul v-else class="select-mem-list">
              <li v-for="m in selectMemResults" :key="m.id"
                :class="['select-mem-item', selectMemChosen?.id === m.id ? 'chosen' : '']"
                @click="selectMemChosen = m">
                <span :class="['badge', m.type]">{{ m.type }}</span>
                <span class="select-mem-name">{{ m.name }}</span>
                <span v-if="m.description" class="select-mem-desc">{{ m.description }}</span>
              </li>
            </ul>
            <p v-if="memError" class="save-hint err">{{ memError }}</p>
          </div>
          <div class="write-footer">
            <button class="btn-cancel" @click="addMemoryOpen = false">{{ t('Cancel') }}</button>
            <button class="btn-save" :disabled="isMemSaving || !selectMemChosen" @click="submitLinkMemory">
              {{ isMemSaving ? t('Linking…') : t('Link') }}
            </button>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, nextTick, provide } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { BASE, apiFetch, apiJSON } from './api.js'
import { useAppStore } from './stores/app.js'
import AppHeader from './AppHeader.vue'
import ProjectIconStrip from './ProjectIconStrip.vue'
import IconClose from './icons/IconClose.svg'
import SkeletonTreePanel from './SkeletonTreePanel.vue'
import NodeDetailPanel from './NodeDetailPanel.vue'
import ContextMenu from './ContextMenu.vue'
import MemoryDetailModal from './MemoryDetailModal.vue'

const router = useRouter()
const appStore = useAppStore()
const { isDark, lang, loginOpen, loginInput, loginError, loginLoading } = storeToRefs(appStore)
const { t, toggleTheme, toggleLang } = appStore
provide('t', t)

// ── Auth (delegates to store) ─────────────────────────────────────────────────
async function submitLogin() {
  const ok = await appStore.submitLogin(BASE)
  if (ok) await loadProjects()
}

async function skipLogin() {
  const ok = await appStore.skipLogin(BASE)
  if (ok) await loadProjects()
}

async function logout() {
  await appStore.logout(BASE)
}

const detailMemory = ref(null)

// ── Projects ──────────────────────────────────────────────────────────────────
const LS_PROJECT_KEY = 'mo_selected_project'
const projects = ref([])
const selectedProject = ref(null)
watch(selectedProject, p => { if (p) localStorage.setItem(LS_PROJECT_KEY, p.slug) })

async function loadProjects() {
  try {
    const r = await apiFetch(`${BASE}/projects`)
    if (r.status === 401) { loginOpen.value = true; return }
    projects.value = await r.json()
  } catch { loginOpen.value = true }
}

async function selectProject(p) {
  selectedProject.value = p
  selectedNode.value = null
  nodeMemories.value = []
  await loadSkeleton(p.id)
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
    const p = await apiJSON(`${BASE}/projects`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ slug, display_name: newProjectName.value }),
    })
    newProjectOpen.value = false
    await loadProjects()
    await selectProject(p)
  } catch (e) { alert(e.message) }
  finally { isCreatingProject.value = false }
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
  skeletonTree.value = await apiJSON(`${BASE}/projects/${projectId}/skeleton`)
}

async function selectNode(node) {
  selectedNode.value = node
  nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${node.id}/memories`)
  memoryCountMap.value = { ...memoryCountMap.value, [node.id]: nodeMemories.value.length }
}

// ── Patch / delete ────────────────────────────────────────────────────────────
async function onPatch({ id, patch }) {
  await apiFetch(`${BASE}/skeleton-nodes/${id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  await loadSkeleton(selectedProject.value.id)
  if (selectedNode.value?.id === id) {
    const updated = flatNodes.value.find(n => n.id === id)
    if (updated) selectedNode.value = updated
  }
}

async function onDelete(nodeId) {
  if (!confirm(t('Delete this node and unlink its memories?'))) return
  const r = await apiFetch(`${BASE}/skeleton-nodes/${nodeId}`, { method: 'DELETE' })
  if (r.status === 409) { alert(t('Built-in nodes cannot be deleted.')); return }
  if (selectedNode.value?.id === nodeId) { selectedNode.value = null; nodeMemories.value = [] }
  await loadSkeleton(selectedProject.value.id)
}

async function onSaveHint(hint) {
  await onPatch({ id: selectedNode.value.id, patch: { prompt_hint: hint } })
}

async function onUpdateTags(tags) {
  await onPatch({ id: selectedNode.value.id, patch: { tags } })
  if (selectedNode.value) selectedNode.value = { ...selectedNode.value, tags }
}

async function onReorder(orderedIds) {
  await apiFetch(`${BASE}/skeleton-nodes/reorder`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: selectedProject.value.id, ordered_ids: orderedIds }),
  })
  await loadSkeleton(selectedProject.value.id)
}

async function unlinkMemory(memoryId) {
  await apiFetch(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories/${memoryId}`, { method: 'DELETE' })
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

async function onAddChild() {
  closeContextMenu()
  if (!ctxNode.value) return
  const name = prompt(t('Child node name:'))
  if (!name?.trim()) return
  await apiJSON(`${BASE}/skeleton-nodes`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ project_id: selectedProject.value.id, parent_id: ctxNode.value.id, name: name.trim() }),
  })
  await loadSkeleton(selectedProject.value.id)
}

function onRenameNode() {
  closeContextMenu()
  if (!ctxNode.value) return
  const name = prompt(t('New name:'), ctxNode.value.name)
  if (name?.trim() && name !== ctxNode.value.name) {
    onPatch({ id: ctxNode.value.id, patch: { name: name.trim() } })
  }
}

function focusTags() {
  closeContextMenu()
  if (ctxNode.value) selectNode(ctxNode.value)
}

async function onDeleteNode() {
  const node = ctxNode.value
  closeContextMenu()
  if (node) await onDelete(node.id)
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
      selectMemResults.value = await apiJSON(`${BASE}/memories?project_slug=${slug}&q=${q}&limit=30`)
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
    const mem = await apiJSON(`${BASE}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...memForm.value, project_id: selectedProject.value.id }),
    })
    await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: mem.id }),
    })
    addMemoryOpen.value = false
    nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`)
    memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
  } catch (e) { memError.value = e.message }
  finally { isMemSaving.value = false }
}

async function submitLinkMemory() {
  if (!selectMemChosen.value) return
  isMemSaving.value = true; memError.value = ''
  try {
    await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: selectMemChosen.value.id }),
    })
    addMemoryOpen.value = false
    nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`)
    memoryCountMap.value = { ...memoryCountMap.value, [selectedNode.value.id]: nodeMemories.value.length }
  } catch (e) { memError.value = e.message }
  finally { isMemSaving.value = false }
}

// ── Init ──────────────────────────────────────────────────────────────────────
onMounted(async () => {
  const r = await apiFetch(`${BASE}/projects`)
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
.sk-app { width: 100%; min-height: 100vh; background: var(--bg, #fff); color: var(--fg, #1a1a1a); font-family: 'JetBrains Mono', monospace; box-sizing: border-box; text-align: left; }
.sk-app.dark {
  background:
    repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,212,138,0.009) 2px, rgba(0,212,138,0.009) 3px),
    #010205;
}
.sk-body { display: flex; height: calc(100vh - 41px); overflow: hidden; }
.dark .sk-body { border-top: 1px solid rgba(0,212,138,0.14); }
.tree-empty { width: 220px; flex-shrink: 0; display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #6e7681); font-size: 12px; border-right: 1px solid var(--border, #30363d); }
/* Login */
.login-overlay { display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100; }
.login-modal { background: var(--bg, #fff); border-radius: 8px; padding: 24px; min-width: 300px; display: flex; flex-direction: column; gap: 12px; }
.login-title { font-size: 16px; font-weight: 700; }
.login-input { border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 8px; font-size: 13px; font-family: inherit; }
.login-error { color: #dc2626; font-size: 12px; margin: 0; }
.btn-login { background: var(--accent, #2563eb); color: #fff; border: none; border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
.btn-skip { background: none; border: none; color: var(--fg-muted, #888); cursor: pointer; font-size: 12px; text-decoration: underline; }
/* Modals */
.modal-overlay { display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 50; }
.modal { background: var(--bg, #fff); border-radius: 8px; border: 1px solid var(--border, #ddd); }
.modal-header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border, #ddd); }
.modal-title { font-size: 13px; font-weight: 700; flex: 1; }
.modal-close { background: none; border: none; cursor: pointer; font-size: 14px; color: var(--fg-muted, #888); padding: 2px 4px; }
.sk-input { width: 100%; border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 6px 8px; font-size: 13px; font-family: inherit; background: var(--input-bg, #fff); color: var(--fg, #1a1a1a); }
.btn-save { background: var(--accent, #2563eb); color: #fff; border: none; border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
.btn-save:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-cancel { background: none; border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
/* Write modal */
.write-modal { background: var(--bg, #fff); border-radius: 8px; border: 1px solid var(--border, #ddd); width: 500px; max-height: 80vh; display: flex; flex-direction: column; }
.write-header { display: flex; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border, #ddd); }
.write-title { font-size: 13px; font-weight: 700; flex: 1; }
.write-body { flex: 1; overflow-y: auto; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.write-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; border-top: 1px solid var(--border, #ddd); }
.write-section { display: flex; flex-direction: column; gap: 4px; }
.write-section-grow { flex: 1; }
.write-field-label { font-size: 10px; font-weight: 700; color: var(--fg-muted, #6e7681); text-transform: uppercase; }
.write-input { border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 6px 8px; font-size: 12px; font-family: inherit; background: var(--input-bg, #fff); color: var(--fg, #1a1a1a); }
.write-textarea { resize: vertical; min-height: 80px; }
.write-type-tabs { display: flex; gap: 4px; }
.type-tab { padding: 3px 10px; border-radius: 4px; border: 1px solid var(--border, #ddd); font-size: 11px; cursor: pointer; background: none; color: var(--fg-muted, #888); }
.type-tab.active { background: var(--accent, #2563eb); color: #fff; border-color: transparent; }
.sk-prompt-hint-text { font-size: 11px; color: var(--fg-muted, #888); background: var(--hint-bg, #f8f9fa); padding: 6px 10px; border-radius: 4px; font-style: italic; }
.save-hint.err { color: #dc2626; font-size: 11px; }
/* Modal tabs */
.modal-tabs { display: flex; border-bottom: 1px solid var(--border, #ddd); padding: 0 12px; flex-shrink: 0; }
.modal-tab { background: none; border: none; border-bottom: 2px solid transparent; padding: 8px 14px; font-size: 12px; cursor: pointer; color: var(--fg-muted, #888); margin-bottom: -1px; }
.modal-tab.active { color: var(--accent, #2563eb); border-bottom-color: var(--accent, #2563eb); font-weight: 700; }
/* Select existing */
.select-mem-hint { font-size: 12px; color: var(--fg-muted, #888); padding: 16px 0; text-align: center; }
.select-mem-list { list-style: none; padding: 0; margin: 6px 0 0; display: flex; flex-direction: column; gap: 2px; max-height: 280px; overflow-y: auto; }
.select-mem-item { display: flex; align-items: baseline; gap: 8px; padding: 7px 10px; border-radius: 5px; border: 1px solid transparent; cursor: pointer; }
.select-mem-item:hover { background: var(--hover, #f5f5f5); }
.select-mem-item.chosen { background: var(--active-bg, #e8f0fe); border-color: var(--accent, #2563eb); }
.select-mem-name { font-size: 12px; font-weight: 600; color: var(--fg, #1a1a1a); flex-shrink: 0; }
.select-mem-desc { font-size: 11px; color: var(--fg-muted, #888); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
/* Dark theme vars — aligned with global [data-theme=dark] sci-fi palette */
.dark {
  --bg: #080d17; --fg: #C8E8F2; --fg-muted: #3E6878;
  --border: rgba(0,212,138,0.20);
  --hover: rgba(0,212,138,0.06); --active-bg: rgba(0,212,138,0.13);
  --input-bg: #030608; --btn-bg: rgba(0,212,138,0.08);
  --hint-bg: #030608; --accent: #00D48A;
  --tag-bg: rgba(0,212,138,0.10); --accent-dim: rgba(0,212,138,0.14);
  --tooltip-bg: #090e1a;
}

/* ── Dark sci-fi modal surfaces ── */
[data-theme=dark] .modal,
[data-theme=dark] .write-modal {
  background: var(--surface-2, #050910);
  border-color: rgba(0,212,138,0.18);
  box-shadow: 0 16px 48px rgba(0,0,0,0.80), 0 0 0 1px rgba(0,212,138,0.08);
}
[data-theme=dark] .modal-header,
[data-theme=dark] .write-header,
[data-theme=dark] .modal-tabs,
[data-theme=dark] .write-footer {
  border-color: rgba(0,212,138,0.10);
}
[data-theme=dark] .write-input {
  background: var(--surface-1, #030608);
  border-color: rgba(0,212,138,0.14);
  color: var(--fg, #C8E8F2);
}
[data-theme=dark] .write-input:focus {
  border-color: rgba(0,212,138,0.45);
  box-shadow: 0 0 0 2px rgba(0,212,138,0.10);
  outline: none;
}
[data-theme=dark] .modal-tab.active {
  color: var(--accent, #00D48A);
  border-bottom-color: var(--accent, #00D48A);
}
[data-theme=dark] .select-mem-item:hover {
  background: rgba(0,212,138,0.06);
}
[data-theme=dark] .select-mem-item.chosen {
  background: rgba(0,212,138,0.10);
  border-color: rgba(0,212,138,0.35);
}
[data-theme=dark] .btn-save {
  background: rgba(0,212,138,0.16);
  color: var(--accent, #00D48A);
  border: 1px solid rgba(0,212,138,0.35);
}
[data-theme=dark] .btn-save:hover:not(:disabled) {
  background: rgba(0,212,138,0.24);
  border-color: rgba(0,212,138,0.55);
}
[data-theme=dark] .btn-cancel {
  background: transparent;
  border-color: rgba(0,212,138,0.14);
  color: var(--fg-muted, #3E6878);
}
[data-theme=dark] .btn-cancel:hover {
  border-color: rgba(0,212,138,0.30);
  color: var(--fg, #C8E8F2);
}
[data-theme=dark] .type-tab.active {
  background: rgba(0,212,138,0.16);
  color: var(--accent, #00D48A);
  border-color: rgba(0,212,138,0.35);
}
[data-theme=dark] .sk-prompt-hint-text {
  background: var(--surface-1, #030608);
  border-left: 2px solid rgba(0,212,138,0.30);
  color: var(--fg-muted, #3E6878);
  border-radius: 0 4px 4px 0;
  padding: 6px 10px;
}
[data-theme=dark] .login-modal {
  background: var(--surface-2, #050910);
  border: 1px solid rgba(0,212,138,0.18);
  box-shadow: 0 16px 48px rgba(0,0,0,0.80);
}
</style>
