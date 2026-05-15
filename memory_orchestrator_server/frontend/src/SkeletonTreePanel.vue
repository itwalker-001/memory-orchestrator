<!-- frontend/src/SkeletonTreePanel.vue -->
<template>
  <div class="tree-panel">
    <div class="tree-header">
      <div class="tree-proj-name">{{ projName }}</div>
      <div class="search-wrap">
        <IconSearch width="11" height="11" class="search-icon" aria-hidden="true" />
        <input v-model="searchQuery" class="search-input" :placeholder="t('Search nodes…')" />
        <span v-if="searchQuery" class="search-count">{{ t('{n} results', { n: matchCount }) }}</span>
        <button v-if="searchQuery" class="search-clear" @click="searchQuery = ''">×</button>
      </div>
    </div>

    <ul class="sk-tree tree-scroll">
      <SkNode
        v-for="node in visibleRoots"
        :key="node.id"
        :node="node"
        :selected-id="selectedId"
        :depth="0"
        :class="{ faded: searchQuery && !matchIds.has(node.id) && !hasMatchDescendant(node) }"
        @select="$emit('select', $event)"
        @patch="$emit('patch', $event)"
        @delete="$emit('delete', $event)"
        @context-menu="$emit('context-menu', $event)"
        @reorder="handleReorder"
      />
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, provide, inject } from 'vue'
import SkNode from './SkNode.vue'
import IconSearch from './icons/IconSearch.svg'

const t = inject('t', k => k)

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  projName: { type: String, default: '' },
  memoryCountMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select', 'patch', 'delete', 'context-menu', 'reorder', 'add-child'])

provide('memoryCountMap', computed(() => props.memoryCountMap))

const searchQuery = ref('')

function flattenTree(nodes, acc = []) {
  for (const n of nodes) {
    acc.push(n)
    if (n.children?.length) flattenTree(n.children, acc)
  }
  return acc
}

const flatNodes = computed(() => flattenTree(props.nodes))

const matchIds = computed(() => {
  if (!searchQuery.value) return new Set()
  const q = searchQuery.value.toLowerCase()
  const ids = new Set()
  for (const n of flatNodes.value) {
    if (n.name.toLowerCase().includes(q)) ids.add(n.id)
  }
  return ids
})

const matchCount = computed(() => matchIds.value.size)

function hasMatchDescendant(node) {
  if (matchIds.value.has(node.id)) return true
  return (node.children || []).some(c => hasMatchDescendant(c))
}

const visibleRoots = computed(() => props.nodes)

function handleReorder({ draggedId, targetId, position }) {
  const siblingsRef = findSiblingsContaining(props.nodes, draggedId, targetId)
  if (!siblingsRef) return

  const siblings = [...siblingsRef]
  const fromIdx = siblings.findIndex(n => n.id === draggedId)
  const toIdx = siblings.findIndex(n => n.id === targetId)
  if (fromIdx === -1 || toIdx === -1) return

  const [removed] = siblings.splice(fromIdx, 1)
  const insertAt = position === 'above' ? (fromIdx < toIdx ? toIdx - 1 : toIdx) : (fromIdx < toIdx ? toIdx : toIdx + 1)
  siblings.splice(insertAt, 0, removed)

  emit('reorder', siblings.map(n => n.id))
}

function findSiblingsContaining(nodes, id1, id2) {
  const ids = nodes.map(n => n.id)
  if (ids.includes(id1) && ids.includes(id2)) return nodes
  for (const n of nodes) {
    if (n.children?.length) {
      const found = findSiblingsContaining(n.children, id1, id2)
      if (found) return found
    }
  }
  return null
}
</script>

<style scoped>
.tree-panel {
  width: 220px; flex-shrink: 0;
  background: var(--bg, #0d1117); border-right: 1px solid var(--border, #30363d);
  display: flex; flex-direction: column; overflow: hidden;
}
.tree-header { padding: 10px 10px 6px; border-bottom: 1px solid var(--border, #21262d); flex-shrink: 0; }
.tree-proj-name { font-size: 12px; font-weight: 700; color: var(--fg, #e6edf3); margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.search-wrap {
  display: flex; align-items: center; gap: 5px;
  background: var(--input-bg, #161b22); border: 1px solid var(--border, #30363d);
  border-radius: 5px; padding: 4px 8px;
}
.search-icon { color: var(--fg-muted, #6e7681); flex-shrink: 0; display: block; }
.search-input { background: none; border: none; outline: none; font-size: 11px; color: var(--fg, #c9d1d9); width: 100%; font-family: inherit; }
.search-count { font-size: 9px; color: var(--fg-muted, #6e7681); flex-shrink: 0; white-space: nowrap; }
.search-clear { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 13px; padding: 0; line-height: 1; flex-shrink: 0; }
.tree-scroll { flex: 1; overflow-y: auto; padding: 4px 0; list-style: none; margin: 0; }
.faded { opacity: 0.35; }

/* ── Dark sci-fi enhancements ── */
[data-theme=dark] .tree-panel {
  background:
    repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,212,138,0.007) 2px, rgba(0,212,138,0.007) 3px),
    var(--surface-2, #050910);
  border-right: 1px solid rgba(0,212,138,0.16);
  box-shadow: 1px 0 20px -8px rgba(0,212,138,0.14);
}
[data-theme=dark] .tree-header {
  border-bottom-color: rgba(0,212,138,0.14);
  position: relative;
  overflow: visible;
}
[data-theme=dark] .tree-header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 1px;
  background: linear-gradient(90deg, rgba(0,212,138,0.75), transparent 65%);
  pointer-events: none;
}
[data-theme=dark] .tree-header::after {
  content: '';
  position: absolute;
  bottom: 0; left: 0;
  width: 50%;
  height: 1px;
  background: linear-gradient(90deg, rgba(0,212,138,0.40), transparent);
  animation: mo-pulse-glow 3.2s ease-in-out infinite;
}
[data-theme=dark] .tree-proj-name {
  color: var(--accent, #00D48A);
  font-family: 'Orbitron', ui-monospace, monospace;
  font-size: 10px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  text-shadow: 0 0 10px rgba(0,212,138,0.40);
}
[data-theme=dark] .search-wrap {
  border-color: rgba(0,212,138,0.18);
}
[data-theme=dark] .search-wrap:focus-within {
  border-color: rgba(0,212,138,0.50);
  box-shadow: 0 0 0 2px rgba(0,212,138,0.10);
}
</style>
