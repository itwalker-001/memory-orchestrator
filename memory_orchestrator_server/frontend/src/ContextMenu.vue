<!-- frontend/src/ContextMenu.vue -->
<template>
  <Teleport to="body">
    <div
      v-if="visible"
      class="ctx-menu"
      :style="menuStyle"
      @click.stop
    >
      <div
        :class="['ctx-item', { disabled: depth >= 2 }]"
        @click="depth < 2 && emit('add-child')"
      >
        <span class="ctx-icon"><IconPlus width="12" height="12" /></span>
        {{ t('Add child node') }}
        <span v-if="depth >= 2" class="ctx-dim">{{ t('Max depth reached') }}</span>
      </div>
      <div class="ctx-item" @click="emit('rename')">
        <span class="ctx-icon"><IconEdit width="12" height="12" /></span>
        {{ t('Rename') }}
        <span class="ctx-shortcut">F2</span>
      </div>
      <div class="ctx-item" @click="emit('manage-tags')">
        <span class="ctx-icon"><IconTag width="12" height="12" /></span>
        {{ t('Manage tags') }}
      </div>
      <div class="ctx-sep"></div>
      <div class="ctx-item danger" @click="emit('delete')">
        <span class="ctx-icon"><IconTrash width="12" height="12" /></span>
        {{ t('Delete node') }}
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, inject } from 'vue'
import IconPlus from './icons/IconPlus.svg'
import IconEdit from './icons/IconEdit.svg'
import IconTag from './icons/IconTag.svg'
import IconTrash from './icons/IconTrash.svg'

const t = inject('t', k => k)

const props = defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['add-child', 'rename', 'manage-tags', 'delete', 'close'])

const menuStyle = computed(() => {
  const w = 160, h = 160
  const left = props.x + w > window.innerWidth ? props.x - w : props.x
  const top = props.y + h > window.innerHeight ? props.y - h : props.y
  return { position: 'fixed', left: left + 'px', top: top + 'px', zIndex: 9999 }
})
</script>

<style scoped>
.ctx-menu {
  background: var(--tooltip-bg, #161b22); border: 1px solid var(--border, #30363d);
  border-radius: 8px; padding: 4px; min-width: 160px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.6);
}
.ctx-item {
  display: flex; align-items: center; gap: 8px; padding: 6px 10px;
  font-size: 11px; border-radius: 5px; cursor: pointer; color: var(--fg, #c9d1d9);
}
.ctx-item:hover:not(.disabled) { background: var(--btn-bg, #21262d); }
.ctx-item.disabled { color: var(--fg-muted, #6e7681); cursor: not-allowed; }
.ctx-item.danger { color: #ff7b72; }
.ctx-item.danger:hover { background: #ff7b7211; }
.ctx-icon { width: 16px; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.ctx-shortcut { margin-left: auto; font-size: 9px; color: var(--fg-muted, #6e7681); background: var(--btn-bg, #21262d); padding: 1px 5px; border-radius: 3px; }
.ctx-dim { margin-left: auto; font-size: 9px; color: var(--fg-muted, #6e7681); }
.ctx-sep { height: 1px; background: var(--border, #30363d); margin: 3px 6px; }
</style>
