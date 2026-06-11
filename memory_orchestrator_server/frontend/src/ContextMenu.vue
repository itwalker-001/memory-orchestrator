<!-- frontend/src/ContextMenu.vue -->
<template>
  <n-dropdown
    trigger="manual"
    placement="bottom-start"
    :show="visible"
    :x="x"
    :y="y"
    :options="options"
    @select="onSelect"
    @clickoutside="emit('close')"
  />
</template>

<script setup>
import { computed, h, inject } from 'vue'
import { NDropdown, NIcon } from 'naive-ui'
import { IconPlus, IconTrash } from './icons.js'

const t = inject('t', k => k)

const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  depth: { type: Number, default: 0 },
  isBuiltin: { type: Boolean, default: false },
})

const emit = defineEmits(['add-child', 'rename', 'delete', 'close'])

function renderIcon(icon) {
  return () => h('span', {
    style: {
      width: '16px',
      height: '16px',
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      lineHeight: '0',
      verticalAlign: 'middle',
    },
  }, [
    h(NIcon, {
      size: 15,
      style: {
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        lineHeight: '0',
      },
    }, { default: () => h(icon) }),
  ])
}

const options = computed(() => [
  { label: t('Add child node'), key: 'add-child', icon: renderIcon(IconPlus), disabled: props.depth >= 2 },
  { type: 'divider', key: 'd1' },
  { label: t('Delete node'), key: 'delete', icon: renderIcon(IconTrash), disabled: props.isBuiltin },
])

function onSelect(key) {
  emit(key)
  emit('close')
}
</script>
