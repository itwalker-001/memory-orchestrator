<!-- frontend/src/NodeDetailPanel.vue -->
<template>
  <div class="detail-panel" v-if="node">
    <div class="detail-header">
      <span class="detail-icon"><component :is="nodeIcon" width="16" height="16" /></span>
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
          <li
            v-for="m in memories" :key="m.id"
            :class="['mem-item', m.type]"
            @click="$emit('open-detail', m)"
          >
            <div class="mc-head">
              <span class="mc-badge">{{ m.type }}</span>
              <span class="mc-name">{{ m.name }}</span>
              <div class="mc-importance">
                <div v-for="i in 5" :key="i" :class="['mc-dot', i <= (m.importance || 3) ? 'on' : 'off']"></div>
              </div>
              <button class="btn-unlink" @click.stop="$emit('unlink-memory', m.id)" title="取消关联">×</button>
            </div>
            <div class="mc-body">
              <div v-if="m.description" class="mc-desc">{{ m.description }}</div>
              <div v-if="m.content" class="mc-content">{{ m.content }}</div>
            </div>
            <div class="mc-foot">
              <span v-for="tag in (m.tags || []).slice(0, 2)" :key="tag" class="mc-tag">{{ tag }}</span>
              <div class="mc-meta">
                <span v-if="m.created_at" class="mc-date">{{ formatDate(m.created_at) }}</span>
              </div>
            </div>
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
import { NODE_ICON_MAP, DEFAULT_NODE_ICON } from './icons/nodeIcons.js'

const t = inject('t', k => k)

const props = defineProps({
  node: { type: Object, default: null },
  memories: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['save-hint', 'update-tags', 'add-memory', 'unlink-memory', 'open-detail'])

const nodeIcon = computed(() => NODE_ICON_MAP[props.node?.name] || DEFAULT_NODE_ICON)

const hintDraft = ref(props.node?.prompt_hint || '')
watch(() => props.node?.id, () => { hintDraft.value = props.node?.prompt_hint || '' })

function saveHint() {
  if (hintDraft.value !== props.node?.prompt_hint) {
    emit('save-hint', hintDraft.value)
  }
}

function formatDate(iso) {
  return iso ? iso.slice(0, 10) : ''
}
</script>

<style scoped>
/* ── Panel chrome ── */
.detail-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--bg, #fff); }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--fg-muted, #5E7888); font-size: 13px; }
.detail-header {
  display: flex; align-items: center; gap: 8px; padding: 12px 16px 10px;
  border-bottom: 1px solid var(--border, #A8C0D4); flex-shrink: 0;
}
.detail-icon { display: flex; align-items: center; color: var(--accent, #006AFF); flex-shrink: 0; }
.detail-title { font-size: 14px; font-weight: 700; flex: 1; color: var(--fg, #0E1C28); }
.detail-body { flex: 1; overflow-y: auto; padding: 12px 16px; display: flex; flex-direction: column; gap: 14px; }
.detail-section { display: flex; flex-direction: column; gap: 6px; }
.detail-label { font-size: 10px; font-weight: 700; color: var(--fg-muted, #5E7888); text-transform: uppercase; letter-spacing: 0.05em; }
.detail-desc { font-size: 12px; color: var(--fg-muted, #5E7888); line-height: 1.5; margin: 0; }
.sk-input { border: 1px solid var(--border, #A8C0D4); border-radius: 5px; padding: 6px 8px; font-size: 12px; font-family: inherit; background: var(--input-bg, #ffffff); color: var(--fg, #0E1C28); width: 100%; outline: none; }
.sk-input:focus { border-color: var(--accent, #006AFF); }
.btn-sm { padding: 4px 10px; border-radius: 5px; border: 1px solid transparent; font-size: 11px; cursor: pointer; }
.btn-primary { background: var(--accent, #006AFF); color: #fff; }

/* ── Memory Cards — Light base ── */
.mem-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }

.mem-item {
  background: #ffffff;
  border: 1px solid rgba(168,192,212,0.42);
  border-radius: 4px;
  position: relative; overflow: hidden; cursor: pointer;
  height: 148px; display: flex; flex-direction: column;
  transition: border-color 0.20s, box-shadow 0.20s, background 0.20s, transform 0.20s;
}
.mem-item::before {
  content: ''; position: absolute;
  top: 0; left: 3px; right: 0; height: 1px;
  background: linear-gradient(90deg, rgba(255,255,255,0.90), transparent 55%);
  pointer-events: none; z-index: 1;
}
.mem-item::after {
  content: ''; position: absolute;
  left: 0; top: 0; bottom: 0; width: 3px;
  border-radius: 4px 0 0 4px; pointer-events: none;
}
.mem-item.feedback::after  { background: linear-gradient(180deg, rgba(230,90,20,0.88),  rgba(230,90,20,0.35)); }
.mem-item.project::after   { background: linear-gradient(180deg, rgba(50,130,230,0.88),  rgba(50,130,230,0.35)); }
.mem-item.reference::after { background: linear-gradient(180deg, rgba(0,165,105,0.88),   rgba(0,165,105,0.35)); }
.mem-item.user::after      { background: linear-gradient(180deg, rgba(140,90,210,0.88),  rgba(140,90,210,0.35)); }
.mem-item.feedback  { box-shadow: 0 1px 8px -2px rgba(230,90,20,0.10); }
.mem-item.project   { box-shadow: 0 1px 8px -2px rgba(50,130,230,0.10); }
.mem-item.reference { box-shadow: 0 1px 8px -2px rgba(0,165,105,0.10); }
.mem-item.user      { box-shadow: 0 1px 8px -2px rgba(140,90,210,0.10); }
.mem-item:hover { background: var(--hover, #f0f4f8); transform: translateY(-2px); }
.mem-item.feedback:hover  { border-color: rgba(230,90,20,0.32);  box-shadow: 0 6px 22px -4px rgba(230,90,20,0.20),  inset 0 0 0 1px rgba(230,90,20,0.08); }
.mem-item.project:hover   { border-color: rgba(50,130,230,0.32);  box-shadow: 0 6px 22px -4px rgba(50,130,230,0.20),  inset 0 0 0 1px rgba(50,130,230,0.08); }
.mem-item.reference:hover { border-color: rgba(0,165,105,0.32);   box-shadow: 0 6px 22px -4px rgba(0,165,105,0.20),   inset 0 0 0 1px rgba(0,165,105,0.08); }
.mem-item.user:hover      { border-color: rgba(140,90,210,0.32);  box-shadow: 0 6px 22px -4px rgba(140,90,210,0.20),  inset 0 0 0 1px rgba(140,90,210,0.08); }

/* Header */
.mc-head {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px 9px 14px;
  border-bottom: 1px solid rgba(168,192,212,0.20);
  position: relative; flex-shrink: 0;
}
.mc-head::after {
  content: ''; position: absolute;
  bottom: 0; left: 14px; right: 0; height: 1px;
  background: linear-gradient(90deg, rgba(14,28,40,0.06), transparent 65%);
}
.mc-badge {
  font-size: 8px; font-weight: 700; letter-spacing: 0.08em;
  padding: 2px 6px; border-radius: 3px;
  text-transform: uppercase; flex-shrink: 0; border: 1px solid;
}
.mem-item.feedback  .mc-badge { background: rgba(230,90,20,0.09);  color: #c04010; border-color: rgba(230,90,20,0.28); }
.mem-item.project   .mc-badge { background: rgba(50,130,230,0.09);  color: #1a60c0; border-color: rgba(50,130,230,0.28); }
.mem-item.reference .mc-badge { background: rgba(0,165,105,0.09);   color: #007a50; border-color: rgba(0,165,105,0.28); }
.mem-item.user      .mc-badge { background: rgba(140,90,210,0.09);  color: #7030b8; border-color: rgba(140,90,210,0.28); }
.mc-name {
  flex: 1; font-size: 12px; font-weight: 600; color: var(--fg, #0E1C28);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; letter-spacing: -0.022em;
}
.mc-importance { display: flex; gap: 2px; flex-shrink: 0; align-items: center; }
.mc-dot { width: 8px; height: 3px; border-radius: 1px; }
.mc-dot.off { background: rgba(14,28,40,0.10); }
.mem-item.feedback  .mc-dot.on { background: rgba(230,90,20,0.75);  box-shadow: 0 0 4px rgba(230,90,20,0.35); }
.mem-item.project   .mc-dot.on { background: rgba(50,130,230,0.75);  box-shadow: 0 0 4px rgba(50,130,230,0.35); }
.mem-item.reference .mc-dot.on { background: rgba(0,165,105,0.75);   box-shadow: 0 0 4px rgba(0,165,105,0.35); }
.mem-item.user      .mc-dot.on { background: rgba(140,90,210,0.75);  box-shadow: 0 0 4px rgba(140,90,210,0.35); }
.btn-unlink {
  background: none; border: none; color: rgba(14,28,40,0.25); cursor: pointer;
  font-size: 14px; padding: 0 2px; line-height: 1; flex-shrink: 0;
  opacity: 0; transition: opacity 0.15s;
}
.mem-item:hover .btn-unlink { opacity: 1; }
.btn-unlink:hover { color: #cf2d56; }

/* Body */
.mc-body { padding: 10px 12px 10px 14px; flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 8px; }
.mc-desc {
  font-size: 11px; font-style: italic; color: var(--fg-muted, #5E7888); line-height: 1.5;
  padding-left: 8px; overflow: hidden;
  display: -webkit-box; -webkit-line-clamp: 1; -webkit-box-orient: vertical;
}
.mem-item.feedback  .mc-desc { border-left: 1.5px solid rgba(230,90,20,0.30); }
.mem-item.project   .mc-desc { border-left: 1.5px solid rgba(50,130,230,0.30); }
.mem-item.reference .mc-desc { border-left: 1.5px solid rgba(0,165,105,0.30); }
.mem-item.user      .mc-desc { border-left: 1.5px solid rgba(140,90,210,0.30); }
.mc-content {
  font-size: 12px; color: rgba(14,28,40,0.65); line-height: 1.65;
  overflow: hidden; display: -webkit-box;
  -webkit-line-clamp: 2; -webkit-box-orient: vertical;
}

/* Footer */
.mc-foot {
  display: flex; align-items: center; gap: 6px;
  padding: 7px 12px 7px 14px;
  border-top: 1px solid rgba(168,192,212,0.20);
  position: relative; flex-shrink: 0;
}
.mc-tag {
  font-size: 8px; font-weight: 500; padding: 1px 6px;
  border-radius: 10px; letter-spacing: 0.05em; border: 1px solid;
}
.mem-item.feedback  .mc-tag { background: rgba(230,90,20,0.08);  color: rgba(180,60,10,0.70);  border-color: rgba(230,90,20,0.18); }
.mem-item.project   .mc-tag { background: rgba(50,130,230,0.08);  color: rgba(20,80,180,0.70);  border-color: rgba(50,130,230,0.18); }
.mem-item.reference .mc-tag { background: rgba(0,165,105,0.08);   color: rgba(0,120,75,0.70);   border-color: rgba(0,165,105,0.18); }
.mem-item.user      .mc-tag { background: rgba(140,90,210,0.08);  color: rgba(100,50,170,0.70); border-color: rgba(140,90,210,0.18); }
.mc-meta { margin-left: auto; display: flex; align-items: center; }
.mc-date { font-size: 8px; color: rgba(14,28,40,0.30); letter-spacing: 0.04em; }
.mem-item.feedback  .mc-foot::after { content: ''; position: absolute; bottom: 0; right: 0; width: 5px; height: 5px; background: rgba(230,90,20,0.55);  border-radius: 0 0 4px 0; }
.mem-item.project   .mc-foot::after { content: ''; position: absolute; bottom: 0; right: 0; width: 5px; height: 5px; background: rgba(50,130,230,0.55);  border-radius: 0 0 4px 0; }
.mem-item.reference .mc-foot::after { content: ''; position: absolute; bottom: 0; right: 0; width: 5px; height: 5px; background: rgba(0,165,105,0.55);   border-radius: 0 0 4px 0; }
.mem-item.user      .mc-foot::after { content: ''; position: absolute; bottom: 0; right: 0; width: 5px; height: 5px; background: rgba(140,90,210,0.55); border-radius: 0 0 4px 0; }

/* ── Dark theme panel chrome ── */
[data-theme=dark] .detail-panel {
  background:
    repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,212,138,0.007) 2px, rgba(0,212,138,0.007) 3px),
    var(--surface-3, #080d17);
}
[data-theme=dark] .detail-empty {
  flex-direction: column; gap: 20px;
  background:
    radial-gradient(ellipse at 50% 38%, rgba(0,212,138,0.07) 0%, transparent 52%),
    repeating-linear-gradient(0deg, transparent 0, transparent 2px, rgba(0,212,138,0.007) 2px, rgba(0,212,138,0.007) 3px),
    var(--surface-3, #080d17);
}
[data-theme=dark] .detail-empty::before {
  content: ''; width: 56px; height: 56px; border-radius: 50%;
  border: 1.5px solid rgba(0,212,138,0.38);
  box-shadow: 0 0 20px rgba(0,212,138,0.16), inset 0 0 20px rgba(0,212,138,0.05), 0 0 0 10px rgba(0,212,138,0.04);
  flex-shrink: 0; animation: mo-pulse-glow 2.8s ease-in-out infinite;
}
[data-theme=dark] .detail-empty > span {
  font-family: 'JetBrains Mono', monospace; font-size: 10px;
  letter-spacing: 0.20em; text-transform: uppercase;
  color: rgba(0,212,138,0.42); text-shadow: 0 0 8px rgba(0,212,138,0.22);
}
[data-theme=dark] .detail-header { border-bottom-color: rgba(0,212,138,0.14); position: relative; }
[data-theme=dark] .detail-header::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, rgba(0,212,138,0.65), transparent 60%);
  pointer-events: none;
}
[data-theme=dark] .detail-title { letter-spacing: -0.01em; }
[data-theme=dark] .sk-input { background: var(--surface-1, #030608); border-color: rgba(0,212,138,0.16); }
[data-theme=dark] .sk-input:focus { border-color: rgba(0,212,138,0.50); box-shadow: 0 0 0 2px rgba(0,212,138,0.10); }

/* ── Dark theme memory cards ── */
[data-theme=dark] .mem-item { background: var(--surface-card, #0c1120); border-color: rgba(0,212,138,0.10); }
[data-theme=dark] .mem-item::before { background: linear-gradient(90deg, rgba(255,255,255,0.07), transparent 50%); }
[data-theme=dark] .mem-item.feedback::after  { background: linear-gradient(180deg, rgba(255,120,50,0.90),  rgba(255,120,50,0.35)); }
[data-theme=dark] .mem-item.project::after   { background: linear-gradient(180deg, rgba(80,160,255,0.90),  rgba(80,160,255,0.35)); }
[data-theme=dark] .mem-item.reference::after { background: linear-gradient(180deg, rgba(0,212,138,0.90),   rgba(0,212,138,0.35)); }
[data-theme=dark] .mem-item.user::after      { background: linear-gradient(180deg, rgba(190,140,255,0.90), rgba(190,140,255,0.35)); }
[data-theme=dark] .mem-item.feedback  { box-shadow: 0 2px 14px -4px rgba(255,120,50,0.18); }
[data-theme=dark] .mem-item.project   { box-shadow: 0 2px 14px -4px rgba(80,160,255,0.18); }
[data-theme=dark] .mem-item.reference { box-shadow: 0 2px 14px -4px rgba(0,212,138,0.18); }
[data-theme=dark] .mem-item.user      { box-shadow: 0 2px 14px -4px rgba(190,140,255,0.18); }
[data-theme=dark] .mem-item:hover { background: #0e1525; }
[data-theme=dark] .mem-item.feedback:hover  { border-color: rgba(255,120,50,0.35);  box-shadow: 0 8px 28px -4px rgba(255,120,50,0.28),  inset 0 0 0 1px rgba(255,120,50,0.10); }
[data-theme=dark] .mem-item.project:hover   { border-color: rgba(80,160,255,0.35);  box-shadow: 0 8px 28px -4px rgba(80,160,255,0.28),  inset 0 0 0 1px rgba(80,160,255,0.10); }
[data-theme=dark] .mem-item.reference:hover { border-color: rgba(0,212,138,0.35);   box-shadow: 0 8px 28px -4px rgba(0,212,138,0.28),   inset 0 0 0 1px rgba(0,212,138,0.10); }
[data-theme=dark] .mem-item.user:hover      { border-color: rgba(190,140,255,0.35); box-shadow: 0 8px 28px -4px rgba(190,140,255,0.28), inset 0 0 0 1px rgba(190,140,255,0.10); }
[data-theme=dark] .mc-head { border-bottom-color: rgba(0,212,138,0.08); }
[data-theme=dark] .mc-head::after { background: linear-gradient(90deg, rgba(0,212,138,0.16), transparent 65%); }
[data-theme=dark] .mem-item.feedback  .mc-badge { background: rgba(255,120,50,0.12); color: #ff8c50; border-color: rgba(255,120,50,0.28); }
[data-theme=dark] .mem-item.project   .mc-badge { background: rgba(80,160,255,0.12); color: #5bb8ff; border-color: rgba(80,160,255,0.28); }
[data-theme=dark] .mem-item.reference .mc-badge { background: rgba(0,212,138,0.12);  color: #00D48A; border-color: rgba(0,212,138,0.28); }
[data-theme=dark] .mem-item.user      .mc-badge { background: rgba(190,140,255,0.12);color: #c29fff; border-color: rgba(190,140,255,0.28); }
[data-theme=dark] .mc-name { color: #C8E8F2; }
[data-theme=dark] .mc-dot.off { background: rgba(255,255,255,0.07); }
[data-theme=dark] .mem-item.feedback  .mc-dot.on { background: rgba(255,120,50,0.85);  box-shadow: 0 0 5px rgba(255,120,50,0.55); }
[data-theme=dark] .mem-item.project   .mc-dot.on { background: rgba(80,160,255,0.85);  box-shadow: 0 0 5px rgba(80,160,255,0.55); }
[data-theme=dark] .mem-item.reference .mc-dot.on { background: rgba(0,212,138,0.85);   box-shadow: 0 0 5px rgba(0,212,138,0.55); }
[data-theme=dark] .mem-item.user      .mc-dot.on { background: rgba(190,140,255,0.85); box-shadow: 0 0 5px rgba(190,140,255,0.55); }
[data-theme=dark] .btn-unlink { color: rgba(0,212,138,0.35); }
[data-theme=dark] .btn-unlink:hover { color: #ff6b6b; }
[data-theme=dark] .mc-desc { color: #5a8fa0; }
[data-theme=dark] .mem-item.feedback  .mc-desc { border-left-color: rgba(255,120,50,0.28); }
[data-theme=dark] .mem-item.project   .mc-desc { border-left-color: rgba(80,160,255,0.28); }
[data-theme=dark] .mem-item.reference .mc-desc { border-left-color: rgba(0,212,138,0.28); }
[data-theme=dark] .mem-item.user      .mc-desc { border-left-color: rgba(190,140,255,0.28); }
[data-theme=dark] .mc-content { color: #9fc8db; }
[data-theme=dark] .mc-foot { border-top-color: rgba(0,212,138,0.06); }
[data-theme=dark] .mem-item.feedback  .mc-tag { background: rgba(255,120,50,0.10);  color: rgba(255,140,80,0.80);  border-color: rgba(255,120,50,0.22); }
[data-theme=dark] .mem-item.project   .mc-tag { background: rgba(80,160,255,0.10);  color: rgba(91,184,255,0.80);  border-color: rgba(80,160,255,0.22); }
[data-theme=dark] .mem-item.reference .mc-tag { background: rgba(0,212,138,0.10);   color: rgba(0,212,138,0.80);   border-color: rgba(0,212,138,0.22); }
[data-theme=dark] .mem-item.user      .mc-tag { background: rgba(190,140,255,0.10); color: rgba(194,159,255,0.80); border-color: rgba(190,140,255,0.22); }
[data-theme=dark] .mc-date { color: rgba(0,212,138,0.32); }
[data-theme=dark] .mem-item.feedback  .mc-foot::after { background: rgba(255,120,50,0.72); }
[data-theme=dark] .mem-item.project   .mc-foot::after { background: rgba(80,160,255,0.72); }
[data-theme=dark] .mem-item.reference .mc-foot::after { background: rgba(0,212,138,0.72); }
[data-theme=dark] .mem-item.user      .mc-foot::after { background: rgba(190,140,255,0.72); }
</style>
