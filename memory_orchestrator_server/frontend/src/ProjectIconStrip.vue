<!-- frontend/src/ProjectIconStrip.vue -->
<template>
  <div class="icon-strip" :style="cssVars">
    <n-tooltip v-for="p in projects" :key="p.id" placement="right" :delay="300">
      <template #trigger>
        <button
          :class="['proj-icon', { active: p.id === activeId }]"
          @click="$emit('select', p)"
          @contextmenu.prevent="$emit('context-menu', { x: $event.clientX, y: $event.clientY, project: p })"
        >
          {{ initials(p.display_name || p.slug) }}
        </button>
      </template>
      {{ p.display_name || p.slug }}
    </n-tooltip>
    <div class="strip-divider"></div>
    <n-tooltip placement="right" :delay="300">
      <template #trigger>
        <button class="proj-icon add-btn" @click="$emit('create')">
          <n-icon :size="18"><IconPlus /></n-icon>
        </button>
      </template>
      {{ t('New project') }}
    </n-tooltip>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { NTooltip, NIcon, useThemeVars } from 'naive-ui'
import { IconPlus } from './icons.js'

const t = inject('t', k => k)

defineProps({
  projects: { type: Array, default: () => [] },
  activeId: { type: String, default: null },
})
defineEmits(['select', 'create', 'context-menu'])

const vars = useThemeVars()
const cssVars = computed(() => ({
  '--strip-bg': vars.value.cardColor,
  '--border': vars.value.borderColor,
  '--btn-bg': vars.value.actionColor,
  '--hover': vars.value.hoverColor,
  '--active-bg': vars.value.primaryColorSuppl,
  '--fg': vars.value.textColor1,
  '--fg-muted': vars.value.textColor3,
  '--accent': vars.value.primaryColor,
}))

function initials(name) {
  return name.split(/[\s\-_\/]/).map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?'
}
</script>

<style scoped>
.icon-strip {
  width: 52px; flex-shrink: 0;
  background: var(--strip-bg); border-right: 1px solid var(--border);
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 0; gap: 5px; overflow-y: auto;
}
.proj-icon {
  width: 32px; height: 32px; border-radius: 7px; border: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; cursor: pointer;
  color: var(--fg-muted); background: var(--btn-bg);
  transition: all 0.15s; flex-shrink: 0;
}
.proj-icon:hover { background: var(--hover); color: var(--fg); }
.proj-icon.active { color: var(--accent); box-shadow: 0 0 0 1.5px var(--accent); }
.add-btn { color: var(--accent); background: transparent; }
.strip-divider { width: 24px; height: 1px; background: var(--border); margin: 2px 0; flex-shrink: 0; }
</style>
