<template>
  <div class="sk-app" :class="{ dark: isDark }">
    <!-- Login overlay (same as App.vue) -->
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
      <header class="sk-header">
        <span class="sk-logo">Memory Orchestrator</span>
        <nav class="sk-nav">
          <router-link to="/memories" class="sk-nav-link">→ Memories</router-link>
        </nav>
        <div class="sk-header-right">
          <button @click="isDark = !isDark" class="btn-icon" title="Toggle theme">◑</button>
        </div>
      </header>

      <div class="sk-body">
        <!-- Left: project list -->
        <aside class="sk-sidebar">
          <div class="sk-sidebar-title">Projects</div>
          <ul class="sk-project-list">
            <li v-for="p in projects" :key="p.id"
              :class="['sk-project-item', { active: selectedProject?.id === p.id }]"
              @click="selectProject(p)">
              {{ p.display_name || p.slug }}
              <span class="sk-mem-count">{{ p.memory_count }}</span>
            </li>
          </ul>
          <div v-if="showNewProject" class="sk-new-project-form">
            <input v-model="newProjectName" class="sk-input" placeholder="Project name…"
              @keydown.enter="createProject" ref="newProjectInput" />
            <button class="btn-sm btn-primary" :disabled="!newProjectName || isCreatingProject"
              @click="createProject">
              {{ isCreatingProject ? '…' : 'Create' }}
            </button>
            <button class="btn-sm" @click="showNewProject = false">✕</button>
          </div>
          <button v-else class="btn-new-project" @click="openNewProject">+ New Project</button>
        </aside>

        <!-- Right: skeleton tree -->
        <main class="sk-main" v-if="selectedProject">
          <div class="sk-main-header">
            <span class="sk-project-title">{{ selectedProject.display_name || selectedProject.slug }}</span>
            <button class="btn-sm btn-secondary" @click="openTokenModal">+ Token</button>
            <button class="btn-sm btn-danger" @click="confirmDeleteProject">Delete Project</button>
          </div>

          <div class="sk-skeleton" v-if="skeletonTree.length">
            <div class="sk-tree-title">Skeleton</div>
            <ul class="sk-tree">
              <sk-node
                v-for="node in skeletonTree" :key="node.id"
                :node="node"
                :selected-node-id="selectedNode?.id"
                @select="selectNode"
                @patch="patchNode"
                @delete="deleteNode"
              />
            </ul>
          </div>

          <!-- Node detail -->
          <div class="sk-node-detail" v-if="selectedNode">
            <div class="sk-node-detail-title">{{ selectedNode.name }}</div>
            <div class="sk-prompt-hint-wrap">
              <label class="sk-field-label">Prompt hint</label>
              <input class="sk-input" v-model="editingPromptHint"
                @blur="savePromptHint" @keydown.enter="savePromptHint"
                placeholder="Guide text shown when creating memories in this section…" />
            </div>
            <div class="sk-node-memories-header">
              <span class="sk-field-label">Memories ({{ nodeMemories.length }})</span>
              <button class="btn-sm btn-primary" @click="openAddMemory">+ Add Memory</button>
            </div>
            <ul class="sk-memory-list">
              <li v-for="m in nodeMemories" :key="m.id" class="sk-memory-item">
                <span :class="['badge', m.type]">{{ m.type }}</span>
                <span class="sk-mem-name">{{ m.name }}</span>
                <button class="btn-icon btn-danger-sm" @click="unlinkMemory(m.id)" title="Unlink">✕</button>
              </li>
            </ul>
          </div>
        </main>

        <main class="sk-main sk-main-empty" v-else>
          <p>Select or create a project to see its skeleton.</p>
        </main>
      </div>
    </template>

    <!-- Add Memory Modal -->
    <div v-if="addMemoryOpen" class="modal-overlay" @click.self="addMemoryOpen = false">
      <div class="write-modal">
        <div class="write-header">
          <span class="write-title">New Memory → {{ selectedNode?.name }}</span>
          <button class="modal-close" @click="addMemoryOpen = false">✕</button>
        </div>
        <div class="write-body">
          <p v-if="selectedNode?.prompt_hint" class="sk-prompt-hint-text">
            {{ selectedNode.prompt_hint }}
          </p>
          <div class="write-type-tabs">
            <button v-for="tp in ['user','feedback','project','reference']" :key="tp"
              :class="['type-tab', 'type-tab-'+tp, memForm.type === tp ? 'active' : '']"
              @click="memForm.type = tp">{{ tp }}</button>
          </div>
          <div class="write-section">
            <label class="write-field-label">Name</label>
            <input class="write-input" v-model="memForm.name" placeholder="Short identifier…" />
          </div>
          <div class="write-section">
            <label class="write-field-label">Description</label>
            <input class="write-input" v-model="memForm.description" placeholder="One-line summary…" />
          </div>
          <div class="write-section write-section-grow">
            <label class="write-field-label">Content</label>
            <textarea class="write-input write-textarea" v-model="memForm.content" rows="5" />
          </div>
          <div v-if="memForm.type === 'feedback' || memForm.type === 'project'" class="write-section">
            <label class="write-field-label">Why</label>
            <input class="write-input" v-model="memForm.why" placeholder="Reason…" />
          </div>
          <div v-if="memForm.type === 'feedback' || memForm.type === 'project'" class="write-section">
            <label class="write-field-label">How to apply</label>
            <input class="write-input" v-model="memForm.how_to_apply" placeholder="When / how to use…" />
          </div>
          <p v-if="memError" class="save-hint err">{{ memError }}</p>
        </div>
        <div class="write-footer">
          <button class="btn-cancel" @click="addMemoryOpen = false">Cancel</button>
          <button class="btn-save" :disabled="isMemSaving || !memForm.name || !memForm.content"
            @click="submitAddMemory">
            {{ isMemSaving ? 'Saving…' : 'Write' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Token Modal -->
    <div v-if="tokenModalOpen" class="modal-overlay" @click.self="tokenModalOpen = false">
      <div class="modal" style="max-width:420px">
        <div class="modal-header">
          <span class="modal-title">New Project Token</span>
          <button class="modal-close" @click="tokenModalOpen = false">✕</button>
        </div>
        <div style="padding:16px;display:flex;flex-direction:column;gap:10px">
          <input class="sk-input" v-model="newTokenName" placeholder="Token name…" />
          <div v-if="!newTokenValue">
            <button class="btn-save" :disabled="!newTokenName || isCreatingToken" @click="createToken">
              {{ isCreatingToken ? 'Creating…' : 'Create Token' }}
            </button>
          </div>
          <div v-else class="token-reveal">
            <p style="color:var(--warn);font-size:12px">Shown once — copy now!</p>
            <code class="token-code" @click="copyToken">{{ newTokenValue }}</code>
            <button class="btn-sm" @click="copyToken">Copy</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { BASE, apiFetch, apiJSON } from './api.js'

// ── Theme ──
const isDark = ref(document.documentElement.classList.contains('dark') ||
  window.matchMedia('(prefers-color-scheme: dark)').matches)
watch(isDark, v => document.documentElement.classList.toggle('dark', v))

// ── Auth ──
const loginOpen = ref(false)
const loginInput = ref('')
const loginError = ref('')
const loginLoading = ref(false)

async function submitLogin() {
  loginLoading.value = true
  loginError.value = ''
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: loginInput.value }),
    })
    if (r.status === 401) { loginError.value = 'Invalid token'; return }
    loginOpen.value = false
    loginInput.value = ''
    await loadProjects()
  } catch (e) { loginError.value = e.message }
  finally { loginLoading.value = false }
}

async function skipLogin() {
  loginLoading.value = true
  try {
    const r = await fetch(`${BASE}/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: '' }),
    })
    if (r.status === 401) { loginError.value = 'Server requires a token'; return }
    loginOpen.value = false
    await loadProjects()
  } finally { loginLoading.value = false }
}

// ── Projects ──
const projects = ref([])
const selectedProject = ref(null)

async function loadProjects() {
  try {
    const r = await apiFetch(`${BASE}/projects`)
    if (r.status === 401) { loginOpen.value = true; return }
    projects.value = await r.json()
  } catch (e) { loginOpen.value = true }
}

function selectProject(p) {
  selectedProject.value = p
  selectedNode.value = null
  nodeMemories.value = []
  loadSkeleton(p.id)
}

const showNewProject = ref(false)
const newProjectName = ref('')
const isCreatingProject = ref(false)
const newProjectInput = ref(null)

function openNewProject() {
  showNewProject.value = true
  newProjectName.value = ''
  setTimeout(() => newProjectInput.value?.focus(), 50)
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
    showNewProject.value = false
    newProjectName.value = ''
    await loadProjects()
    selectProject(p)
  } catch (e) { alert(e.message) }
  finally { isCreatingProject.value = false }
}

async function confirmDeleteProject() {
  if (!selectedProject.value) return
  if (!confirm(`Delete project "${selectedProject.value.display_name}"?`)) return
  await apiFetch(`${BASE}/projects/${selectedProject.value.id}`, { method: 'DELETE' })
  selectedProject.value = null
  skeletonTree.value = []
  await loadProjects()
}

// ── Skeleton ──
const skeletonTree = ref([])
const selectedNode = ref(null)
const nodeMemories = ref([])
const editingPromptHint = ref('')

async function loadSkeleton(projectId) {
  const tree = await apiJSON(`${BASE}/projects/${projectId}/skeleton`)
  skeletonTree.value = tree
}

function selectNode(node) {
  selectedNode.value = node
  editingPromptHint.value = node.prompt_hint || ''
  loadNodeMemories(node.id)
}

async function loadNodeMemories(nodeId) {
  nodeMemories.value = await apiJSON(`${BASE}/skeleton-nodes/${nodeId}/memories`)
}

async function savePromptHint() {
  if (!selectedNode.value) return
  await apiFetch(`${BASE}/skeleton-nodes/${selectedNode.value.id}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt_hint: editingPromptHint.value }),
  })
  selectedNode.value.prompt_hint = editingPromptHint.value
  loadSkeleton(selectedProject.value.id)
}

async function patchNode(nodeId, patch) {
  await apiFetch(`${BASE}/skeleton-nodes/${nodeId}`, {
    method: 'PATCH', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  })
  await loadSkeleton(selectedProject.value.id)
}

async function deleteNode(nodeId) {
  if (!confirm('Delete this node and unlink its memories?')) return
  const r = await apiFetch(`${BASE}/skeleton-nodes/${nodeId}`, { method: 'DELETE' })
  if (r.status === 409) { alert('Cannot delete a builtin node.'); return }
  if (selectedNode.value?.id === nodeId) { selectedNode.value = null; nodeMemories.value = [] }
  await loadSkeleton(selectedProject.value.id)
}

async function unlinkMemory(memoryId) {
  await apiFetch(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories/${memoryId}`, { method: 'DELETE' })
  await loadNodeMemories(selectedNode.value.id)
}

// ── Add Memory ──
const addMemoryOpen = ref(false)
const isMemSaving = ref(false)
const memError = ref('')
const memForm = ref({ type: 'project', name: '', description: '', content: '', why: '', how_to_apply: '' })

function openAddMemory() {
  memForm.value = { type: 'project', name: '', description: '', content: '', why: '', how_to_apply: '' }
  memError.value = ''
  addMemoryOpen.value = true
}

async function submitAddMemory() {
  if (!memForm.value.name || !memForm.value.content) return
  isMemSaving.value = true
  memError.value = ''
  try {
    const payload = { ...memForm.value, project_id: selectedProject.value.id }
    if (!payload.why) delete payload.why
    if (!payload.how_to_apply) delete payload.how_to_apply
    const mem = await apiJSON(`${BASE}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    await apiJSON(`${BASE}/skeleton-nodes/${selectedNode.value.id}/memories`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ memory_id: mem.id }),
    })
    addMemoryOpen.value = false
    await loadNodeMemories(selectedNode.value.id)
  } catch (e) { memError.value = e.message }
  finally { isMemSaving.value = false }
}

// ── Token ──
const tokenModalOpen = ref(false)
const newTokenName = ref('')
const newTokenValue = ref('')
const isCreatingToken = ref(false)

function openTokenModal() {
  newTokenName.value = ''
  newTokenValue.value = ''
  tokenModalOpen.value = true
}

async function createToken() {
  isCreatingToken.value = true
  try {
    const data = await apiJSON(`${BASE}/tokens`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ kind: 'project_token', name: newTokenName.value, project_id: selectedProject.value.id }),
    })
    newTokenValue.value = data.token
  } catch (e) { alert(e.message) }
  finally { isCreatingToken.value = false }
}

async function copyToken() {
  await navigator.clipboard.writeText(newTokenValue.value)
}

// ── Init ──
onMounted(async () => {
  const r = await apiFetch(`${BASE}/projects`)
  if (r.status === 401) { loginOpen.value = true; return }
  projects.value = await r.json()
})
</script>

<script>
// SkNode recursive component for skeleton tree
export default {
  components: {
    SkNode: {
      name: 'SkNode',
      props: ['node', 'selectedNodeId'],
      emits: ['select', 'patch', 'delete'],
      data() { return { hovering: false, editing: false, editName: '' } },
      methods: {
        startEdit() { this.editName = this.node.name; this.editing = true },
        saveEdit() {
          if (this.editName && this.editName !== this.node.name)
            this.$emit('patch', this.node.id, { name: this.editName })
          this.editing = false
        },
      },
      template: `
        <li class="sk-node" @mouseenter="hovering=true" @mouseleave="hovering=false">
          <div :class="['sk-node-row', { active: selectedNodeId === node.id }]"
            @click="$emit('select', node)">
            <span v-if="!editing" class="sk-node-name">{{ node.name }}</span>
            <input v-else class="sk-node-edit-input" v-model="editName"
              @blur="saveEdit" @keydown.enter="saveEdit" @keydown.esc="editing=false" ref="ei"
              @vue:mounted="$refs.ei?.focus()" />
            <span class="sk-node-actions" v-show="hovering">
              <button class="btn-icon-xs" @click.stop="startEdit" title="Edit">✎</button>
              <button v-if="!node.is_builtin" class="btn-icon-xs btn-danger-xs"
                @click.stop="$emit('delete', node.id)" title="Delete">✕</button>
            </span>
          </div>
          <ul v-if="node.children?.length" class="sk-tree sk-subtree">
            <sk-node v-for="c in node.children" :key="c.id" :node="c"
              :selected-node-id="selectedNodeId"
              @select="$emit('select', $event)"
              @patch="(id, p) => $emit('patch', id, p)"
              @delete="$emit('delete', $event)" />
          </ul>
        </li>
      `,
    },
  },
}
</script>

<style scoped>
.sk-app { min-height: 100vh; background: var(--bg, #fff); color: var(--fg, #1a1a1a); font-family: 'JetBrains Mono', monospace; }
.sk-header { display: flex; align-items: center; gap: 12px; padding: 10px 20px; border-bottom: 1px solid var(--border, #e0e0e0); }
.sk-logo { font-weight: 700; font-size: 14px; }
.sk-nav { margin-left: auto; }
.sk-nav-link { font-size: 12px; color: var(--accent, #2563eb); text-decoration: none; }
.sk-nav-link:hover { text-decoration: underline; }
.sk-header-right { display: flex; gap: 8px; }
.sk-body { display: grid; grid-template-columns: 220px 1fr; height: calc(100vh - 41px); }
.sk-sidebar { border-right: 1px solid var(--border, #e0e0e0); padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; }
.sk-sidebar-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--fg-muted, #6e7681); margin-bottom: 6px; }
.sk-project-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 2px; }
.sk-project-item { padding: 6px 8px; border-radius: 5px; cursor: pointer; font-size: 13px; display: flex; justify-content: space-between; align-items: center; }
.sk-project-item:hover { background: var(--hover, #f5f5f5); }
.sk-project-item.active { background: var(--active-bg, #dbeafe); color: var(--accent, #2563eb); }
.sk-mem-count { font-size: 11px; color: var(--fg-muted, #6e7681); }
.sk-new-project-form { display: flex; gap: 4px; margin-top: 6px; }
.btn-new-project { margin-top: 8px; font-size: 12px; color: var(--accent, #2563eb); background: none; border: 1px dashed var(--border, #ccc); border-radius: 5px; padding: 5px 8px; cursor: pointer; width: 100%; }
.sk-main { padding: 16px 20px; overflow-y: auto; }
.sk-main-empty { display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #999); font-size: 13px; }
.sk-main-header { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; }
.sk-project-title { font-size: 16px; font-weight: 700; flex: 1; }
.sk-tree-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--fg-muted, #6e7681); margin-bottom: 8px; }
.sk-tree { list-style: none; padding: 0; margin: 0; }
.sk-subtree { padding-left: 16px; }
.sk-node-row { display: flex; align-items: center; padding: 5px 6px; border-radius: 4px; cursor: pointer; font-size: 13px; gap: 6px; }
.sk-node-row:hover { background: var(--hover, #f5f5f5); }
.sk-node-row.active { background: var(--active-bg, #dbeafe); }
.sk-node-name { flex: 1; }
.sk-node-actions { display: flex; gap: 4px; }
.sk-node-edit-input { flex: 1; border: 1px solid var(--border, #ccc); border-radius: 3px; padding: 1px 4px; font-size: 12px; }
.sk-node-detail { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border, #e0e0e0); }
.sk-node-detail-title { font-size: 15px; font-weight: 700; margin-bottom: 10px; }
.sk-prompt-hint-wrap { margin-bottom: 12px; }
.sk-field-label { display: block; font-size: 11px; font-weight: 600; color: var(--fg-muted, #6e7681); margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.04em; }
.sk-input { width: 100%; border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 6px 8px; font-size: 13px; font-family: inherit; background: var(--input-bg, #fff); color: var(--fg, #1a1a1a); }
.sk-node-memories-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px; }
.sk-memory-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.sk-memory-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border: 1px solid var(--border, #eee); border-radius: 5px; font-size: 12px; }
.sk-mem-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-icon { background: none; border: none; cursor: pointer; padding: 3px 5px; font-size: 13px; color: var(--fg-muted, #666); }
.btn-icon:hover { color: var(--fg, #1a1a1a); }
.btn-sm { padding: 4px 10px; border-radius: 5px; border: 1px solid var(--border, #ccc); font-size: 12px; cursor: pointer; background: var(--btn-bg, #f5f5f5); color: var(--fg, #1a1a1a); }
.btn-primary { background: var(--accent, #2563eb); color: #fff; border-color: transparent; }
.btn-secondary { background: transparent; border-color: var(--accent, #2563eb); color: var(--accent, #2563eb); }
.btn-danger { background: transparent; border-color: #dc2626; color: #dc2626; }
.btn-icon-xs { background: none; border: none; cursor: pointer; padding: 1px 3px; font-size: 11px; color: var(--fg-muted, #888); }
.btn-icon-xs:hover { color: var(--fg, #1a1a1a); }
.btn-danger-xs { color: #dc2626; }
.btn-danger-sm { padding: 1px 4px; font-size: 11px; background: none; border: none; color: #dc2626; cursor: pointer; }
.sk-prompt-hint-text { font-size: 12px; color: var(--fg-muted, #888); background: var(--hint-bg, #f8f9fa); padding: 8px 10px; border-radius: 4px; margin-bottom: 10px; font-style: italic; }
.token-reveal { display: flex; flex-direction: column; gap: 6px; }
.token-code { display: block; padding: 8px; background: var(--code-bg, #f5f5f5); border-radius: 4px; font-size: 11px; word-break: break-all; cursor: pointer; border: 1px solid var(--border, #ddd); }
.dark { --bg: #0d1117; --fg: #e6edf3; --fg-muted: #8b949e; --border: #30363d; --hover: #161b22; --active-bg: #1d2d3e; --input-bg: #161b22; --btn-bg: #21262d; --hint-bg: #161b22; --code-bg: #161b22; --accent: #58a6ff; --warn: #f0883e; }
/* Login styles */
.login-overlay { display: flex; align-items: center; justify-content: center; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 100; }
.login-modal { background: var(--bg, #fff); border-radius: 8px; padding: 24px; min-width: 300px; display: flex; flex-direction: column; gap: 12px; }
.login-title { font-size: 16px; font-weight: 700; }
.login-input { border: 1px solid var(--border, #ddd); border-radius: 5px; padding: 8px; font-size: 13px; font-family: inherit; }
.login-error { color: #dc2626; font-size: 12px; margin: 0; }
.btn-login { background: var(--accent, #2563eb); color: #fff; border: none; border-radius: 5px; padding: 8px 16px; cursor: pointer; font-size: 13px; }
.btn-skip { background: none; border: none; color: var(--fg-muted, #888); cursor: pointer; font-size: 12px; text-decoration: underline; }
</style>
