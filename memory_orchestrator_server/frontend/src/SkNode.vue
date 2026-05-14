<!-- frontend/src/SkNode.vue -->
<template>
  <li
    class="sk-node"
    :draggable="true"
    @dragstart.stop="onDragStart"
    @dragover.stop.prevent="onDragOver"
    @dragleave.stop="onDragLeave"
    @drop.stop="onDrop"
    @dragend.stop="onDragEnd"
  >
    <div
      :class="['sk-node-row', { active: selectedId === node.id, dragging: isDragging, 'drop-above': isDragOver === 'above', 'drop-below': isDragOver === 'below' }]"
      @click="$emit('select', node)"
      @contextmenu.prevent="onContextMenu"
      @mouseenter="startTooltip"
      @mouseleave="cancelTooltip"
    >
      <span class="sk-drag-handle">⠿</span>
      <span class="sk-chevron" @click.stop="toggleExpand">
        <span v-if="node.children?.length">{{ expanded ? '▼' : '▶' }}</span>
        <span v-else style="opacity:0">▶</span>
      </span>
      <span class="sk-emoji">{{ nodeEmoji }}</span>
      <div class="sk-node-body">
        <div class="sk-node-name-row">
          <span v-if="!editing" class="sk-node-name">{{ node.name }}</span>
          <input
            v-else
            ref="editInput"
            class="sk-node-edit-input"
            v-model="editName"
            @blur="saveEdit"
            @keydown.enter="saveEdit"
            @keydown.esc="editing = false"
          />
          <span v-if="memCount > 0" class="sk-node-badge">{{ memCount }}</span>
        </div>
      </div>
    </div>

    <!-- Tooltip via Teleport -->
    <Teleport to="body">
      <div v-if="showTooltip" class="sk-tooltip" :style="tooltipStyle">
        <div class="sk-tooltip-name">{{ nodeEmoji }} {{ node.name }}</div>
        <div v-if="node.prompt_hint" class="sk-tooltip-hint">{{ node.prompt_hint.slice(0, 80) }}</div>
        <div class="sk-tooltip-stats">
          <span>{{ t('Memories') }}: {{ memCount }}</span>
          <span>{{ t('Child nodes') }}: {{ node.children?.length || 0 }}</span>
        </div>
        <div v-if="node.tags?.length" class="sk-tooltip-tags">
          <span v-for="t in node.tags" :key="t" class="sk-tooltip-tag">{{ t }}</span>
        </div>
      </div>
    </Teleport>

    <!-- Children -->
    <ul v-if="expanded && node.children?.length" class="sk-tree sk-subtree">
      <SkNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :selected-id="selectedId"
        :depth="depth + 1"
        @select="$emit('select', $event)"
        @patch="$emit('patch', $event)"
        @delete="$emit('delete', $event)"
        @context-menu="$emit('context-menu', $event)"
        @reorder="$emit('reorder', $event)"
      />
    </ul>
  </li>
</template>

<script setup>
import { ref, computed, nextTick, inject } from 'vue'

const props = defineProps({
  node: { type: Object, required: true },
  selectedId: { type: String, default: null },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['select', 'patch', 'delete', 'context-menu', 'reorder'])

// ── Expand/collapse ──────────────────────────────────────────────────────────
const expanded = ref(true)
function toggleExpand() { expanded.value = !expanded.value }

// ── Emoji map ────────────────────────────────────────────────────────────────
const EMOJI_MAP = {
  '项目概况': '📌', '需求': '📋', '设计': '🎨', '技术栈': '🔧',
  '前端': '🖥', '后端': '⚙️', '数据库': '🗄️', '测试': '🧪',
  '部署': '🚀', '决策记录': '📝', '经验库': '💡',
}
const nodeEmoji = computed(() => EMOJI_MAP[props.node.name] || '📄')

// ── i18n ─────────────────────────────────────────────────────────────────────
const t = inject('t', k => k)

// ── Memory count ─────────────────────────────────────────────────────────────
const memoryCountMap = inject('memoryCountMap', {})
const memCount = computed(() => memoryCountMap[props.node.id] || 0)

// ── Inline edit ──────────────────────────────────────────────────────────────
const editing = ref(false)
const editName = ref('')
const editInput = ref(null)

function startEdit() {
  if (props.node.is_builtin) return
  editName.value = props.node.name
  editing.value = true
  nextTick(() => editInput.value?.focus())
}

function saveEdit() {
  if (editName.value && editName.value !== props.node.name) {
    emit('patch', { id: props.node.id, patch: { name: editName.value } })
  }
  editing.value = false
}

defineExpose({ startEdit, forceExpand: () => { expanded.value = true } })

// ── Context menu ─────────────────────────────────────────────────────────────
function onContextMenu(e) {
  emit('context-menu', { x: e.clientX, y: e.clientY, node: props.node, depth: props.depth })
}

// ── Tooltip ──────────────────────────────────────────────────────────────────
const showTooltip = ref(false)
const tooltipStyle = ref({})
let tooltipTimer = null

function startTooltip(e) {
  tooltipTimer = setTimeout(() => {
    const rect = e.currentTarget.getBoundingClientRect()
    tooltipStyle.value = {
      position: 'fixed',
      left: rect.right + 10 + 'px',
      top: rect.top + 'px',
      zIndex: 9999,
    }
    showTooltip.value = true
  }, 500)
}

function cancelTooltip() {
  clearTimeout(tooltipTimer)
  showTooltip.value = false
}

// ── Drag and drop ────────────────────────────────────────────────────────────
const isDragging = ref(false)
const isDragOver = ref(null)

function onDragStart(e) {
  isDragging.value = true
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', props.node.id)
}

function onDragOver(e) {
  const rect = e.currentTarget.getBoundingClientRect()
  const mid = rect.top + rect.height / 2
  isDragOver.value = e.clientY < mid ? 'above' : 'below'
}

function onDragLeave() {
  isDragOver.value = null
}

function onDrop(e) {
  const draggedId = e.dataTransfer.getData('text/plain')
  if (draggedId === props.node.id) { isDragOver.value = null; return }
  emit('reorder', { draggedId, targetId: props.node.id, position: isDragOver.value })
  isDragOver.value = null
}

function onDragEnd() {
  isDragging.value = false
  isDragOver.value = null
}
</script>

<style scoped>
.sk-node { list-style: none; }
.sk-node-row {
  display: flex; align-items: center; padding: 3px 6px; border-radius: 4px;
  cursor: pointer; font-size: 12px; gap: 3px; user-select: none;
  border-top: 2px solid transparent; border-bottom: 2px solid transparent;
}
.sk-node-row:hover { background: var(--hover, #161b22); }
.sk-node-row.active { background: var(--active-bg, #1d2d3e); }
.sk-node-row.active .sk-node-name { color: var(--accent, #58a6ff); }
.sk-node-row.dragging { opacity: 0.4; }
.sk-node-row.drop-above { border-top-color: var(--accent, #58a6ff); }
.sk-node-row.drop-below { border-bottom-color: var(--accent, #58a6ff); }
.sk-drag-handle { color: var(--fg-muted, #6e7681); font-size: 10px; cursor: grab; flex-shrink: 0; }
.sk-chevron { font-size: 8px; color: var(--fg-muted, #6e7681); width: 12px; text-align: center; flex-shrink: 0; }
.sk-emoji { font-size: 12px; flex-shrink: 0; }
.sk-node-body { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.sk-node-name-row { display: flex; align-items: center; gap: 4px; min-width: 0; }
.sk-node-name { flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--fg, #c9d1d9); }
.sk-node-edit-input { flex: 1; border: 1px solid var(--accent, #58a6ff); border-radius: 3px; padding: 1px 4px; font-size: 12px; background: var(--input-bg, #161b22); color: var(--fg, #e6edf3); }
.sk-node-badge { font-size: 9px; color: var(--fg-muted, #6e7681); background: var(--btn-bg, #21262d); border-radius: 8px; padding: 1px 5px; flex-shrink: 0; }
.sk-tree { list-style: none; padding: 0; margin: 0; }
.sk-subtree { padding-left: 16px; }
.sk-tooltip {
  background: var(--tooltip-bg, #1c2128); border: 1px solid var(--border, #30363d);
  border-radius: 8px; padding: 10px 12px; max-width: 240px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.5); pointer-events: none;
}
.sk-tooltip-name { font-size: 12px; font-weight: 700; color: var(--fg, #e6edf3); margin-bottom: 4px; }
.sk-tooltip-hint { font-size: 10px; color: var(--fg-muted, #8b949e); margin-bottom: 6px; font-style: italic; line-height: 1.5; }
.sk-tooltip-stats { display: flex; gap: 12px; font-size: 10px; color: var(--fg-muted, #6e7681); margin-bottom: 4px; }
.sk-tooltip-tags { display: flex; gap: 4px; flex-wrap: wrap; }
.sk-tooltip-tag { font-size: 9px; background: var(--tag-bg, #1a3a52); color: var(--accent, #58a6ff); border-radius: 3px; padding: 1px 4px; }
</style>
