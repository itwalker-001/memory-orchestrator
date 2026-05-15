<!-- frontend/src/NodeDetailPanel.vue -->
<template>
  <div class="detail-panel" v-if="node">
    <div class="detail-header">
      <span class="detail-emoji">{{ nodeEmoji }}</span>
      <span class="detail-title">{{ node.name }}</span>
      <button class="btn-sm btn-primary" @click="$emit('add-memory')">{{ t('+ Add memory') }}</button>
    </div>

    <div class="detail-body">
      <!-- Tags -->
      <section class="detail-section">
        <div class="detail-label">{{ t('Tags') }}</div>
        <TagPicker
          :model-value="node.tags || []"
          :all-tags="allTags"
          @update:model-value="$emit('update-tags', $event)"
        />
      </section>

      <!-- Description -->
      <section v-if="node.description" class="detail-section">
        <div class="detail-label">{{ t('Description') }}</div>
        <p class="detail-desc">{{ node.description }}</p>
      </section>

      <!-- Prompt hint -->
      <section class="detail-section">
        <div class="detail-label">Prompt Hint</div>
        <input
          class="sk-input"
          :value="hintDraft"
          @input="hintDraft = $event.target.value"
          @blur="saveHint"
          @keydown.enter="saveHint"
          :placeholder="t('Prompt hint…')"
        />
      </section>

      <!-- Memories -->
      <section class="detail-section">
        <div class="detail-label">{{ t('Memories ({n})', { n: memories.length }) }}</div>
        <ul class="mem-list">
          <li v-for="m in memories" :key="m.id" class="mem-item" @click="$emit('open-detail', m)">
            <span :class="['badge', m.type]">{{ m.type }}</span>
            <span class="mem-name" :title="m.description">{{ m.name }}</span>
            <button class="btn-unlink" @click.stop="$emit('unlink-memory', m.id)" title="取消关联">×</button>
          </li>
        </ul>
      </section>
    </div>
  </div>
  <div class="detail-empty" v-else>
    <span>{{ t('Select a node to view details') }}</span>
  </div>
</template>

<script setup>
import { ref, watch, computed, inject } from 'vue'
import TagPicker from './TagPicker.vue'

const t = inject('t', k => k)

const props = defineProps({
  node: { type: Object, default: null },
  memories: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['save-hint', 'update-tags', 'add-memory', 'unlink-memory', 'open-detail'])

const EMOJI_MAP = {
  '项目概况': '📌', '需求': '📋', '设计': '🎨', '技术栈': '🔧',
  '前端': '💻', '后端': '🔩', '数据库': '💾', '测试': '🧪',
  '部署': '🚀', '决策记录': '📝', '经验库': '💡',
}
const nodeEmoji = computed(() => EMOJI_MAP[props.node?.name] || '📄')

const hintDraft = ref(props.node?.prompt_hint || '')
watch(() => props.node?.id, () => { hintDraft.value = props.node?.prompt_hint || '' })

function saveHint() {
  if (hintDraft.value !== props.node?.prompt_hint) {
    emit('save-hint', hintDraft.value)
  }
}
</script>

<style scoped>
.detail-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg, #0d1117); }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #6e7681); font-size: 13px; }
.detail-header {
  display: flex; align-items: center; gap: 8px; padding: 12px 16px 10px;
  border-bottom: 1px solid var(--border, #21262d); flex-shrink: 0;
}
.detail-emoji { font-size: 18px; }
.detail-title { font-size: 14px; font-weight: 700; flex: 1; color: var(--fg, #e6edf3); }
.detail-body { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 14px; }
.detail-section { display: flex; flex-direction: column; gap: 6px; }
.detail-label { font-size: 10px; font-weight: 700; color: var(--fg-muted, #6e7681); text-transform: uppercase; letter-spacing: 0.05em; }
.sk-input { border: 1px solid var(--border, #30363d); border-radius: 5px; padding: 6px 8px; font-size: 12px; font-family: inherit; background: var(--input-bg, #161b22); color: var(--fg, #e6edf3); width: 100%; outline: none; }
.sk-input:focus { border-color: var(--accent, #58a6ff); }
.detail-desc { font-size: 12px; color: var(--fg-muted, #8b949e); line-height: 1.5; margin: 0; }
.mem-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 4px; }
.mem-item { display: flex; align-items: center; gap: 8px; padding: 5px 8px; border: 1px solid var(--border, #21262d); border-radius: 5px; font-size: 12px; cursor: pointer; }
.mem-item:hover { background: var(--row-hover, rgba(0,0,0,0.04)); }
.mem-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fg, #c9d1d9); }
.btn-unlink { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 14px; padding: 0 2px; line-height: 1; }
.btn-unlink:hover { color: #ff7b72; }
.badge { font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 3px; flex-shrink: 0; }
.badge.feedback { background: #3a2a10; color: #f0883e; }
.badge.project { background: #1a2a3a; color: #58a6ff; }
.badge.reference { background: #1a2a1a; color: #3fb950; }
.badge.user { background: #2a1a3a; color: #d2a8ff; }
.btn-sm { padding: 4px 10px; border-radius: 5px; border: 1px solid transparent; font-size: 11px; cursor: pointer; }
.btn-primary { background: var(--accent, #2563eb); color: #fff; }
</style>
