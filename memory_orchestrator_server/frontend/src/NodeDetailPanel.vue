<!-- frontend/src/NodeDetailPanel.vue -->
<template>
  <div class="detail-panel" v-if="node" :style="cssVars">
    <div class="detail-header">
      <div class="detail-header-inner">
        <n-icon :size="18" :component="nodeIcon" class="detail-icon" />
        <n-text strong class="detail-title">{{ node.name }}</n-text>
        <n-button quaternary circle size="small" :title="t('Edit')" @click="$emit('edit-node', node)">
          <template #icon><n-icon :size="15"><IconEdit /></n-icon></template>
        </n-button>
      </div>
    </div>

    <n-scrollbar class="detail-body">
      <div class="detail-inner">
      <!-- Tags -->
      <section class="detail-section">
        <n-text depth="3" class="detail-label">{{ t('Tags') }}</n-text>
        <div v-if="node.tags?.length" class="readonly-tags">
          <n-tag v-for="tag in node.tags" :key="tag" size="small" :bordered="false" class="sq-tag">{{ tag }}</n-tag>
        </div>
        <n-text v-else depth="3" class="readonly-empty">-</n-text>
      </section>

      <!-- Description -->
      <section v-if="node.description" class="detail-section">
        <n-text depth="3" class="detail-label">{{ t('Description') }}</n-text>
        <n-text depth="3" style="font-size:12px;line-height:1.5">{{ node.description }}</n-text>
      </section>

      <!-- Prompt hint -->
      <section class="detail-section">
        <n-text depth="3" class="detail-label">{{ t('Prompt Hint') }}</n-text>
        <n-text depth="2" class="readonly-text">{{ node.prompt_hint || '-' }}</n-text>
      </section>

      <!-- Memories -->
      <section class="detail-section">
        <div class="mem-section-head">
          <n-text depth="3" class="detail-label">{{ t('Memories ({n})', { n: memories.length }) }}</n-text>
          <n-button quaternary circle size="small" :title="t('Add memory')" @click="$emit('add-memory')">
            <template #icon><n-icon><IconPlus /></n-icon></template>
          </n-button>
        </div>
        <n-empty v-if="memories.length === 0" size="small" :description="t('No memories yet')" style="padding:12px 0" />
        <div v-else class="mem-list">
          <n-card
            v-for="m in memories" :key="m.id"
            size="small"
            :bordered="false"
            class="mem-card"
            @click="$emit('open-detail', m)"
          >
            <div class="mc-top">
              <span class="mc-type-pill" :class="`mc-type--${m.type}`">{{ t(m.type) }}</span>
              <div class="mc-top-right">
                <n-text class="mc-date">{{ formatDate(m.created_at) }}</n-text>
                <div class="mc-actions">
                  <n-button quaternary circle size="tiny" class="mc-action" :title="t('Edit')" @click.stop="$emit('edit-memory', m)">
                    <template #icon><n-icon :size="13"><IconEdit /></n-icon></template>
                  </n-button>
                  <n-button quaternary circle size="tiny" class="mc-action" :title="t('Unlink')" @click.stop="$emit('unlink-memory', m.id)">
                    <template #icon><n-icon :size="13"><IconClose /></n-icon></template>
                  </n-button>
                </div>
              </div>
            </div>
            <n-text class="mc-name">{{ m.name }}</n-text>
            <p v-if="m.description" class="mc-desc">{{ m.description }}</p>
            <p class="mc-content">{{ m.content }}</p>
            <div class="mc-foot">
              <n-rate readonly size="small" class="mc-stars" :value="m.importance || 3" :count="5" />
              <div class="mc-tags">
                <n-tag v-for="tag in (m.tags || []).slice(0, 3)" :key="tag" size="tiny" :bordered="false" class="mc-tag">{{ tag }}</n-tag>
              </div>
            </div>
          </n-card>
        </div>
      </section>
      </div>
    </n-scrollbar>
  </div>
  <n-empty v-else class="detail-empty" :description="t('Select a node to view details')" />
</template>

<script setup>
import { computed, inject } from 'vue'
import { NIcon, NText, NButton, NScrollbar, NCard, NTag, NRate, NEmpty, useThemeVars } from 'naive-ui'
import { NODE_ICON_MAP, DEFAULT_NODE_ICON } from './icons/nodeIcons.js'
import { IconPlus, IconClose, IconEdit } from './icons.js'

const t = inject('t', k => k)

const props = defineProps({
  node: { type: Object, default: null },
  memories: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['save-hint', 'update-tags', 'add-memory', 'unlink-memory', 'open-detail', 'edit-memory', 'edit-node'])

const vars = useThemeVars()
const isDark = computed(() => vars.value.name === 'dark' || /rgb\(\s*(?:1[0-9]|2[0-9]|3[0-9])\b/.test(vars.value.bodyColor))
const cssVars = computed(() => {
  const dark = isDark.value
  return {
    '--panel-bg': vars.value.bodyColor,
    '--border': vars.value.borderColor,
    '--accent': vars.value.primaryColor,
    '--muted': vars.value.textColor3,
    '--hover-shadow': vars.value.boxShadow2,
    // Card surface: lift above the page background so it reads as an elevated
    // panel. Dark mode uses an explicit elevation step (#242424 over #121212).
    '--mc-card-bg': dark ? '#242424' : '#FFFFFF',
    '--mc-card-border': dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
    '--mc-card-hover-border': dark
      ? 'color-mix(in srgb, var(--accent) 55%, rgba(255,255,255,0.06))'
      : 'color-mix(in srgb, var(--accent) 40%, rgba(0,0,0,0.04))',
    '--mc-title': dark ? '#E2E8F0' : '#1F2937',
    '--mc-content': dark ? '#A1A1AA' : '#475467',
    '--mc-meta': dark ? '#71717A' : 'var(--accent)',
    // type pill: project → de-saturated mint that fits either theme
    '--mc-project-bg': dark ? '#0F5B3E' : '#E6F4EA',
    '--mc-project-fg': dark ? '#86EFAC' : '#137333',
    '--mc-feedback-bg': dark ? '#10463A' : '#E7F3EF',
    '--mc-feedback-fg': dark ? '#6EE7B7' : '#287D63',
    '--mc-reference-bg': dark ? '#4A3410' : '#FBF1E3',
    '--mc-reference-fg': dark ? '#FCD34D' : '#B45309',
    '--mc-user-bg': dark ? '#27272A' : '#F1F3F5',
    '--mc-user-fg': dark ? '#A1A1AA' : '#475467',
    '--mc-star-active': '#D97706',
    '--mc-star-inactive': dark ? '#444444' : '#E5E7EB',
  }
})

const nodeIcon = computed(() => NODE_ICON_MAP[props.node?.name] || DEFAULT_NODE_ICON)

function formatDate(iso) {
  return iso ? iso.slice(0, 10) : ''
}

</script>

<style scoped>
.detail-panel { flex: 1; display: flex; flex-direction: column; overflow: hidden; background: var(--panel-bg); }
.detail-empty { flex: 1; display: flex; align-items: center; justify-content: center; }

/* Header — shares the same max-width column as the body so the action button
   aligns with the content's right edge instead of floating to the far edge.
   Inspector measure capped at 760px (Linear-style readable column). */
.detail-header { padding: 14px 24px; border-bottom: 1px solid var(--border); flex-shrink: 0; }
.detail-header-inner { display: flex; align-items: center; gap: 10px; }
.detail-icon { flex-shrink: 0; color: var(--accent); }
.detail-title { font-size: 15px; letter-spacing: -0.01em; flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.detail-body { flex: 1; }
.detail-inner { display: flex; flex-direction: column; gap: 24px; padding: 22px 24px; }

.detail-section { display: flex; flex-direction: column; gap: 8px; }
/* Eyebrow-style section label (Linear eyebrow: uppercase, positive tracking, muted) */
.detail-label { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); }
.readonly-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; min-height: 22px; }
.readonly-text { font-size: 12px; line-height: 1.6; }
.readonly-empty { font-size: 12px; line-height: 1.6; }

.mem-section-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 28px; }
.mem-list { columns: 2; column-gap: 16px; }
@media (max-width: 900px) { .mem-list { columns: 1; } }

/* Memory card — Notion/Linear-style: airy padding, soft ambient shadow,
   title as the primary focal point, mint-green hover lift. Colors are driven
   by --mc-* vars so light/dark each get a tuned palette (set in cssVars). */
.mem-card {
  cursor: pointer;
  break-inside: avoid;
  margin-bottom: 16px;
  border-radius: 8px;
  background: var(--mc-card-bg);
  border: 1px solid var(--mc-card-border);
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04), 0 4px 16px rgba(16, 24, 40, 0.04);
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
}
.mem-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 2px 4px rgba(16, 24, 40, 0.05), 0 12px 28px rgba(16, 24, 40, 0.08);
  border-color: var(--mc-card-hover-border);
}
.mem-card :deep(.n-card__content) { display: flex; flex-direction: column; gap: 8px; padding: 20px; }
.mem-card.n-card { border-radius: 8px; }

/* Top row: type pill left, timestamp + actions right */
.mc-top { display: flex; align-items: center; justify-content: space-between; gap: 8px; min-height: 20px; }
.mc-top-right { display: flex; align-items: center; gap: 6px; }
.mc-type-pill {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  padding: 4px 9px;
  border-radius: 4px;
  letter-spacing: 0.02em;
  background: var(--mc-user-bg);
  color: var(--mc-user-fg);
}
/* De-saturated, system-aligned type colors — no pure blue / bright yellow. */
.mc-type--project   { background: var(--mc-project-bg); color: var(--mc-project-fg); }
.mc-type--feedback  { background: var(--mc-feedback-bg); color: var(--mc-feedback-fg); }
.mc-type--reference { background: var(--mc-reference-bg); color: var(--mc-reference-fg); }
.mc-type--user      { background: var(--mc-user-bg); color: var(--mc-user-fg); }

.mc-actions { display: flex; align-items: center; gap: 2px; }
.mc-action { flex-shrink: 0; opacity: 0; transition: opacity 0.15s; }
.mem-card:hover .mc-action { opacity: 1; }

/* Title — the absolute first focal point. */
.mc-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--mc-title);
  line-height: 1.4;
  letter-spacing: -0.01em;
  margin-top: 2px;
}

.mc-desc {
  font-size: 12px;
  font-style: italic;
  line-height: 1.6;
  color: var(--mc-content);
  opacity: 0.85;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
/* Fixed 2-line clamp at 1.6 line-height → uniform block height across all cards. */
.mc-content {
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--mc-content);
  margin: 0;
  min-height: calc(12.5px * 1.6 * 2);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.mc-foot { display: flex; align-items: center; gap: 8px; margin-top: 4px; padding-top: 12px; border-top: 1px solid color-mix(in srgb, var(--border) 50%, transparent); }
/* Softened amber stars; inactive stars are a neutral grey tuned per theme. */
.mc-stars {
  flex-shrink: 0;
  --n-item-size: 13px;
  --n-item-color-active: var(--mc-star-active);
  --n-item-color: var(--mc-star-inactive);
}
.mc-tags { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin-left: auto; }
:deep(.sq-tag.n-tag), :deep(.mc-tag.n-tag) { border-radius: 4px; }
.mc-date { font-size: 11px; color: var(--mc-meta); font-variant-numeric: tabular-nums; }

@media (prefers-reduced-motion: reduce) {
  .mem-card, .mc-action { transition: none; }
  .mem-card:hover { transform: none; }
}

</style>
