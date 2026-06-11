<script setup>
import { ref, computed, watch } from 'vue'
import { NModal, NIcon, NText, NScrollbar, NCollapse, NCollapseItem, NRate, useThemeVars } from 'naive-ui'
import { renderMarkdown } from './markdown.js'
import { apiJSON, copyText } from './api.js'
import { useAppStore } from './stores/app.js'
import { IconEdit, IconClose } from './icons.js'

const props = defineProps({
  memory: { type: Object, default: null },
})
const emit = defineEmits(['close', 'edit'])

const { t } = useAppStore()

const vars = useThemeVars()
const isDark = computed(() => /rgb\(\s*(?:1[0-9]|2[0-9]|3[0-9])\b/.test(vars.value.bodyColor))

const cssVars = computed(() => {
  const dark = isDark.value
  return {
    '--dm-accent': vars.value.primaryColor,
    '--dm-shell-bg': dark ? '#1B1B1F' : '#FFFFFF',
    '--dm-shell-border': dark ? 'rgba(255,255,255,0.07)' : 'rgba(0,0,0,0.06)',
    '--dm-header-divider': dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.05)',
    '--dm-crumb-meta': dark ? '#A1A1AA' : '#9CA3AF',
    '--dm-title': dark ? '#FFFFFF' : '#111827',
    '--dm-text': dark ? '#D4D4D8' : '#374151',
    '--dm-muted': dark ? '#A1A1AA' : '#6B7280',
    '--dm-crumb-bg': dark ? '#27272A' : '#F1F3F5',
    '--dm-crumb-fg': dark ? '#A1A1AA' : '#6B7280',
    '--dm-iconbtn-hover': dark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.05)',
    '--dm-code-bg': dark ? '#121214' : '#F6F8FA',
    '--dm-code-fg': dark ? '#D4D4D8' : '#24292F',
    '--dm-code-comment': dark ? '#6A9955' : '#6A737D',
    '--dm-code-border': dark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.06)',
    '--dm-project-bg': dark ? '#0F5B3E' : '#E6F4EA',
    '--dm-project-fg': dark ? '#86EFAC' : '#137333',
    '--dm-feedback-bg': dark ? '#10463A' : '#E7F3EF',
    '--dm-feedback-fg': dark ? '#6EE7B7' : '#287D63',
    '--dm-reference-bg': dark ? '#4A3410' : '#FBF1E3',
    '--dm-reference-fg': dark ? '#FCD34D' : '#B45309',
    '--dm-user-bg': dark ? '#27272A' : '#F1F3F5',
    '--dm-user-fg': dark ? '#A1A1AA' : '#475467',
    '--dm-star-active': '#D97706',
    '--dm-star-inactive': dark ? '#444444' : '#E5E7EB',
    '--dm-scrollthumb': dark ? 'rgba(255,255,255,0.14)' : 'rgba(0,0,0,0.18)',
  }
})

// The node-memories list endpoint omits heavy fields (content). When the passed
// memory lacks content, fetch the full record so the detail body stays complete.
const full = ref(null)
const view = computed(() => ({ ...(props.memory || {}), ...(full.value || {}) }))

// ── Linked skeleton nodes + full record ──
const nodes = ref([])
watch(() => props.memory, async m => {
  nodes.value = []
  full.value = null
  if (!m) return
  if (m.content === undefined) {
    try { full.value = await apiJSON(`/memories/${m.id}`) } catch { full.value = null }
  }
  try {
    nodes.value = await apiJSON(`/memories/${m.id}/nodes`)
  } catch { nodes.value = [] }
}, { immediate: true })

function md(text) {
  return renderMarkdown(text)
}

const copied = ref(null)
async function copy(text) {
  await copyText(text)
  copied.value = text
  setTimeout(() => { copied.value = null }, 1500)
}

function sourceLabel(source) {
  return source === 'codex' ? 'Codex' : 'Claude Code'
}

const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || null
function fmtDateTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (browserTz) {
    try {
      const parts = new Intl.DateTimeFormat('sv', {
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        timeZoneName: 'short', hour12: false, timeZone: browserTz,
      }).formatToParts(d)
      const get = type => parts.find(p => p.type === type)?.value ?? ''
      const zone = get('timeZoneName')
      return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}${zone ? ' ' + zone : ''}`
    } catch { /* fall through */ }
  }
  return d.toLocaleDateString('sv') + ' ' + d.toLocaleTimeString('en-GB', { hour12: false })
}
</script>

<template>
  <n-modal
    v-if="memory"
    :show="true"
    :mask-closable="true"
    :auto-focus="false"
    transform-origin="center"
    class="dm-modal"
    @update:show="v => { if (!v) emit('close') }"
  >
    <div class="dm-shell" role="dialog" :style="cssVars">
      <!-- Header: title + actions row, then breadcrumb + subtitle as metadata -->
      <header class="dm-header">
        <div class="dm-header-top">
          <h2 class="dm-title">{{ view.name }}</h2>
          <div class="dm-header-actions">
            <span class="dm-type-pill" :class="`dm-type--${view.type}`">{{ t(view.type) }}</span>
            <button class="dm-icon-btn" :title="t('Edit')" @click="emit('edit', memory)">
              <n-icon :size="16"><IconEdit /></n-icon>
            </button>
            <button class="dm-icon-btn" :title="t('Close')" @click="emit('close')">
              <n-icon :size="18"><IconClose /></n-icon>
            </button>
          </div>
        </div>

        <!-- Breadcrumb / linked-node chips: low-key transparent metadata -->
        <div v-if="nodes.length" class="dm-crumbs">
          <span v-for="n in nodes" :key="n.id" class="dm-crumb"
            :title="(n.path || [n.name]).join(' / ')">
            {{ (n.path || [n.name]).join(' / ') }}
          </span>
        </div>

        <p v-if="view.description" class="dm-desc">{{ view.description }}</p>
      </header>

      <n-scrollbar class="dm-scroll" style="max-height: calc(88vh - 200px)">
        <div class="dm-body">
          <div class="dm-block">
            <span class="dm-label">{{ t('Content') }}</span>
            <div class="md-body" v-html="md(view.content)"></div>
          </div>
          <div v-if="view.why" class="dm-block">
            <span class="dm-label">{{ t('Why') }}</span>
            <div class="md-body" v-html="md(view.why)"></div>
          </div>
          <div v-if="view.how_to_apply" class="dm-block">
            <span class="dm-label">{{ t('How to Apply') }}</span>
            <div class="md-body" v-html="md(view.how_to_apply)"></div>
          </div>

          <div class="dm-block">
            <span class="dm-label">{{ t('Importance') }}</span>
            <n-rate readonly :value="view.importance || 1" :count="5" :allow-half="false" size="small" class="dm-rate" />
          </div>

          <div class="dm-meta">
            <span class="dm-meta-text">
              <strong>{{ sourceLabel(view.source_client) }}</strong> · {{ t('Hits') }} <strong>{{ view.hit_count }}</strong>
              <template v-if="view.last_hit_at"> · {{ fmtDateTime(view.last_hit_at) }}</template>
            </span>
          </div>

          <n-collapse>
            <n-collapse-item title="IDs" name="ids">
              <n-text depth="3" style="font-size:11px;display:block">
                ID: <n-text code style="cursor:pointer" @click="copy(view.id)" :title="t('Click to copy')">{{ view.id }}</n-text>
                <span v-if="copied === view.id"> ✓</span>
              </n-text>
              <n-text depth="3" style="font-size:11px;display:block;margin-top:4px">
                Project: <n-text code style="cursor:pointer" @click="copy(view.project_id)" :title="t('Click to copy')">{{ view.project_id }}</n-text>
                <span v-if="copied === view.project_id"> ✓</span>
              </n-text>
            </n-collapse-item>
          </n-collapse>
        </div>
      </n-scrollbar>
    </div>
  </n-modal>
</template>

<style scoped>
/* Frosted overlay — blur the page behind the modal. */
.dm-modal :deep(.n-modal-mask),
:global(.dm-modal + .n-modal-mask),
:global(.n-modal-mask.dm-modal) { backdrop-filter: blur(8px); background: rgba(0, 0, 0, 0.6); }

/* Shell — replaces n-card; controls width, radius, padding, elevation. */
.dm-shell {
  width: 60vw;
  max-width: 768px;
  max-height: 88vh;
  display: flex;
  flex-direction: column;
  background: var(--dm-shell-bg);
  border: 1px solid var(--dm-shell-border);
  border-radius: 8px;
  padding: 32px;
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.4);
  box-sizing: border-box;
}

/* Header container: groups title, breadcrumb and subtitle as one unit,
   separated from the content body by a hairline divider. */
.dm-header {
  display: flex;
  flex-direction: column;
  padding-bottom: 16px;
  margin-bottom: 20px;
  border-bottom: 1px solid var(--dm-header-divider);
}
/* Top row: title left, actions right, vertically centered. */
.dm-header-top { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.dm-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  line-height: 1.3;
  color: var(--dm-title);
  letter-spacing: -0.01em;
  min-width: 0;
  word-break: break-word;
}
.dm-header-actions { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.dm-type-pill {
  font-size: 11px;
  font-weight: 500;
  line-height: 1;
  padding: 5px 10px;
  border-radius: 4px;
  letter-spacing: 0.02em;
  background: var(--dm-crumb-bg);
  color: var(--dm-crumb-fg);
}
.dm-type--project   { background: var(--dm-project-bg); color: var(--dm-project-fg); }
.dm-type--feedback  { background: var(--dm-feedback-bg); color: var(--dm-feedback-fg); }
.dm-type--reference { background: var(--dm-reference-bg); color: var(--dm-reference-fg); }
.dm-type--user      { background: var(--dm-user-bg); color: var(--dm-user-fg); }
/* Modern line icon buttons with a soft hover bubble. */
.dm-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--dm-muted);
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}
.dm-icon-btn:hover { background: var(--dm-iconbtn-hover); color: var(--dm-title); }

/* Breadcrumb: transparent, low-key metadata sitting tight under the title. */
.dm-crumbs { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 6px; }
.dm-crumb {
  font-size: 11px;
  line-height: 1.4;
  color: var(--dm-crumb-meta);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* Cap the scroll viewport so long content scrolls internally instead of
   pushing the shell past 88vh. The max-height is applied inline on the
   <n-scrollbar> element: naive forwards the class but not the scoped
   data-v attribute, so a scoped .dm-scroll rule would never match. */
.dm-scroll { margin-top: 0; }
.dm-body { display: flex; flex-direction: column; gap: 18px; padding-right: 6px; }
.dm-desc { margin: 6px 0 0; font-size: 13px; line-height: 1.6; color: var(--dm-muted); }

.dm-block { display: flex; flex-direction: column; gap: 8px; }
.dm-label {
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--dm-muted);
}
.dm-rate { --n-item-color-active: var(--dm-star-active); --n-item-color: var(--dm-star-inactive); }

.dm-meta { padding-top: 4px; }
.dm-meta-text { font-size: 11px; color: var(--dm-muted); }

/* ── Markdown body ── */
.md-body { font-size: 13px; line-height: 1.6; color: var(--dm-text); }
.md-body :deep(p) { margin: 8px 0; }
.md-body :deep(ul), .md-body :deep(ol) { margin: 8px 0; padding-left: 22px; }
.md-body :deep(ul) { list-style: disc; }
.md-body :deep(ol) { list-style: decimal; }
.md-body :deep(li) { margin: 3px 0; }
/* H2/H3: modest size, generous margins, 3px accent rule on the left. */
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3),
.md-body :deep(h4), .md-body :deep(h5), .md-body :deep(h6) {
  margin: 22px 0 10px;
  padding-left: 12px;
  border-left: 3px solid var(--dm-accent);
  font-weight: 600;
  line-height: 1.35;
  color: var(--dm-title);
}
.md-body :deep(h1) { font-size: 17px; }
.md-body :deep(h2) { font-size: 15px; }
.md-body :deep(h3), .md-body :deep(h4), .md-body :deep(h5), .md-body :deep(h6) { font-size: 13.5px; }
.md-body :deep(h1:first-child), .md-body :deep(h2:first-child), .md-body :deep(h3:first-child) { margin-top: 0; }
.md-body :deep(blockquote) { margin: 10px 0; padding-left: 12px; border-left: 3px solid var(--dm-shell-border); color: var(--dm-muted); }
.md-body :deep(a) { color: var(--dm-accent); text-decoration: none; }
.md-body :deep(a:hover) { text-decoration: underline; }
.md-body :deep(table) { border-collapse: collapse; margin: 10px 0; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid var(--dm-code-border); padding: 5px 9px; }

/* Code blocks / directory trees: container chrome only — Shiki (.shiki) owns
   the background + token colors via the dual-theme binding in style.css. */
.md-body :deep(pre) {
  margin: 12px 0;
  padding: 14px 16px;
  border-radius: 8px;
  border: 1px solid var(--dm-code-border);
  overflow-x: auto;
}
.md-body :deep(pre code) {
  display: block;
  font-family: 'JetBrains Mono', 'Fira Code', 'FiraCode', Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre;
}
/* Inline code keeps a subtle chip look. */
.md-body :deep(:not(pre) > code) {
  font-family: 'JetBrains Mono', 'Fira Code', 'FiraCode', Menlo, Consolas, monospace;
  font-size: 12px;
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--dm-code-bg);
  border: 1px solid var(--dm-code-border);
  color: var(--dm-code-fg);
}

/* Thin, rounded, translucent scrollbar. */
.dm-scroll :deep(.n-scrollbar-rail--vertical) { width: 6px; right: 0; }
.dm-scroll :deep(.n-scrollbar-rail--vertical .n-scrollbar-rail__scrollbar) {
  width: 6px;
  border-radius: 3px;
  background: var(--dm-scrollthumb);
}
</style>
