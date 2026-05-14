<!-- frontend/src/SkeletonTreePanel.vue -->
<template>
  <div class="tree-panel">
    <div class="tree-header">
      <div class="tree-proj-name">{{ projName }}</div>
      <div class="search-wrap">
        <span class="search-icon">🔍</span>
        <input v-model="searchQuery" class="search-input" placeholder="搜索节点…" />
        <span v-if="searchQuery" class="search-count">{{ matchCount }} 结果</span>
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
import { ref, computed, provide } from 'vue'
import SkNode from './SkNode.vue'

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
.search-icon { font-size: 10px; color: var(--fg-muted, #6e7681); flex-shrink: 0; }
.search-input { background: none; border: none; outline: none; font-size: 11px; color: var(--fg, #c9d1d9); width: 100%; font-family: inherit; }
.search-count { font-size: 9px; color: var(--fg-muted, #6e7681); flex-shrink: 0; white-space: nowrap; }
.search-clear { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 13px; padding: 0; line-height: 1; flex-shrink: 0; }
.tree-scroll { flex: 1; overflow-y: auto; padding: 4px 0; list-style: none; margin: 0; }
.faded { opacity: 0.35; }
</style>
