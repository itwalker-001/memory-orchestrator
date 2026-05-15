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
  position: relative;
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

/* Dark sci-fi enhancements */
[data-theme=dark] .icon-strip {
  background: var(--surface-1, #030608);
  border-right: 1px solid rgba(0,212,138,0.18);
  box-shadow: 1px 0 16px -8px rgba(0,212,138,0.12);
}
[data-theme=dark] .icon-strip::before {
  content: '';
  position: absolute;
  top: 0; left: 8px; right: 8px;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0,212,138,0.55), transparent);
  animation: mo-pulse-glow 3.5s ease-in-out infinite;
  pointer-events: none;
}
[data-theme=dark] .proj-icon {
  font-family: 'Orbitron', ui-monospace, monospace;
  font-size: 9px;
  letter-spacing: 0.05em;
}
[data-theme=dark] .proj-icon.active {
  box-shadow: 0 0 0 1.5px var(--accent, #00D48A), 0 0 12px rgba(0,212,138,0.30);
  color: var(--accent, #00D48A);
}
[data-theme=dark] .proj-icon:hover:not(.active) {
  box-shadow: 0 0 6px rgba(0,212,138,0.18);
}
[data-theme=dark] .add-btn {
  color: rgba(0,212,138,0.60);
  font-family: ui-monospace, monospace;
}
[data-theme=dark] .add-btn:hover { color: var(--accent, #00D48A); }
[data-theme=dark] .strip-divider {
  background: rgba(0,212,138,0.15);
}
</style>
