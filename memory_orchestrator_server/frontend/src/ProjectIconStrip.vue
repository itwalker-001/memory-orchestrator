<!-- frontend/src/ProjectIconStrip.vue -->
<template>
  <div class="icon-strip">
    <button
      v-for="p in projects"
      :key="p.id"
      :class="['proj-icon', { active: p.id === activeId }]"
      :title="p.display_name || p.slug"
      @click="$emit('select', p)"
    >
      {{ initials(p.display_name || p.slug) }}
    </button>
    <div class="strip-divider"></div>
    <button class="proj-icon add-btn" :title="t('New project')" @click="$emit('create')">+</button>
  </div>
</template>

<script setup>
import { inject } from 'vue'

const t = inject('t', k => k)

defineProps({
  projects: { type: Array, default: () => [] },
  activeId: { type: String, default: null },
})
defineEmits(['select', 'create'])

function initials(name) {
  return name.split(/[\s\-_\/]/).map(w => w[0]).join('').toUpperCase().slice(0, 2) || '?'
}
</script>

<style scoped>
.icon-strip {
  width: 52px; flex-shrink: 0;
  background: var(--strip-bg, #f0f0f0); border-right: 1px solid var(--border, #30363d);
  display: flex; flex-direction: column; align-items: center;
  padding: 10px 0; gap: 5px; overflow-y: auto;
}
.proj-icon {
  width: 32px; height: 32px; border-radius: 7px; border: none;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 800; cursor: pointer;
  color: var(--fg-muted, #8b949e); background: var(--btn-bg, #161b22);
  transition: all 0.15s; flex-shrink: 0;
}
.proj-icon:hover { background: var(--hover, #21262d); color: var(--fg, #c9d1d9); }
.proj-icon.active { background: var(--active-bg, #1d2d3e); color: var(--accent, #58a6ff); box-shadow: 0 0 0 1.5px var(--accent, #58a6ff); }
.add-btn { font-size: 16px; font-weight: 400; color: #3fb950; }
.add-btn:hover { color: #56d364; }
.strip-divider { width: 24px; height: 1px; background: var(--border, #30363d); margin: 2px 0; flex-shrink: 0; }
</style>
