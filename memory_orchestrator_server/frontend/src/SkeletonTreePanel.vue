<!-- frontend/src/SkeletonTreePanel.vue -->
<template>
  <div class="tree-panel" :style="cssVars">
    <div class="tree-header">
      <div class="tree-title-row">
        <n-text strong class="tree-proj-name">{{ projName }}</n-text>
        <n-button quaternary circle size="tiny" :title="t('Add top-level node')" @click="$emit('add-root')">
          <template #icon><n-icon :size="15"><IconPlus /></n-icon></template>
        </n-button>
      </div>
      <n-input v-model:value="searchQuery" size="small" clearable :placeholder="t('Search nodes…')">
        <template #prefix><n-icon :size="13"><IconSearch /></n-icon></template>
        <template #suffix>
          <n-text v-if="searchQuery" depth="3" style="font-size:10px;white-space:nowrap">{{ matchCount }}</n-text>
        </template>
      </n-input>
    </div>

    <n-scrollbar class="tree-scroll">
      <ul class="sk-tree">
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
    </n-scrollbar>
  </div>
</template>

<script setup>
import { ref, computed, provide, inject } from 'vue'
import { NButton, NIcon, NInput, NScrollbar, NText, useThemeVars } from 'naive-ui'
import SkNode from './SkNode.vue'
import { IconPlus, IconSearch } from './icons.js'

const vars = useThemeVars()
const cssVars = computed(() => ({
  '--panel-bg': vars.value.cardColor,
  '--border': vars.value.borderColor,
}))

const t = inject('t', k => k)

const props = defineProps({
  nodes: { type: Array, default: () => [] },
  selectedId: { type: String, default: null },
  projName: { type: String, default: '' },
  memoryCountMap: { type: Object, default: () => ({}) },
})

const emit = defineEmits(['select', 'patch', 'delete', 'context-menu', 'reorder', 'add-child', 'add-root'])

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
  background: var(--panel-bg); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; overflow: hidden;
}
.tree-header { padding: 10px 10px 8px; border-bottom: 1px solid var(--border); flex-shrink: 0; display: flex; flex-direction: column; gap: 6px; }
.tree-title-row { display: flex; align-items: center; gap: 6px; }
.tree-proj-name { font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; flex: 1; min-width: 0; }
.tree-scroll { flex: 1; min-height: 0; }
.sk-tree { padding: 4px 0; list-style: none; margin: 0; }
.faded { opacity: 0.35; }
</style>
