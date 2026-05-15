<script setup>
import { ref } from 'vue'
import { marked } from 'marked'
import { useLocale } from './useLocale.js'

const props = defineProps({
  memory: { type: Object, default: null },
})
const emit = defineEmits(['close', 'edit'])

const { t } = useLocale()

marked.setOptions({ breaks: true, gfm: true })
function md(text) {
  if (!text) return ''
  return marked.parse(text.replace(/\\n/g, '\n'))
}

const copied = ref(null)
async function copy(text) {
  await navigator.clipboard.writeText(text)
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
      const get = t => parts.find(p => p.type === t)?.value ?? ''
      const zone = get('timeZoneName')
      return `${get('year')}-${get('month')}-${get('day')} ${get('hour')}:${get('minute')}:${get('second')}${zone ? ' ' + zone : ''}`
    } catch { /* fall through */ }
  }
  return d.toLocaleDateString('sv') + ' ' + d.toLocaleTimeString('en-GB', { hour12: false })
}
</script>

<template>
  <Teleport to="body">
    <div v-if="memory" class="modal-overlay" @click.self="emit('close')">
      <div class="detail-modal">
        <div :class="['write-header', 'type-header-' + memory.type]">
          <div style="display:flex;align-items:center;gap:8px;">
            <span :class="['tag', memory.type]" style="font-size:10px;padding:1px 6px">{{ t(memory.type) }}</span>
            <span class="write-title">{{ t('Memory Details') }}</span>
          </div>
          <div class="write-header-right">
            <button class="btn-header-edit" @click="emit('edit', memory)" :title="t('Edit')">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button class="modal-close" @click="emit('close')">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <line x1="1" y1="1" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <line x1="11" y1="1" x2="1" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="detail-modal-body">
          <div class="detail-hero">
            <div class="detail-hero-name">{{ memory.name }}</div>
            <div v-if="memory.description" class="detail-hero-desc">{{ memory.description }}</div>
          </div>
          <div class="content-block">
            <div class="block-label">{{ t('Content') }}</div>
            <div class="md-body" v-html="md(memory.content)"></div>
          </div>
          <div v-if="memory.why" class="content-block">
            <div class="block-label">{{ t('Why') }}</div>
            <div class="md-body" v-html="md(memory.why)"></div>
          </div>
          <div v-if="memory.how_to_apply" class="content-block">
            <div class="block-label">{{ t('How to Apply') }}</div>
            <div class="md-body" v-html="md(memory.how_to_apply)"></div>
          </div>
          <div class="meta-strip">
            <span class="meta-item"><strong>{{ sourceLabel(memory.source_client) }}</strong></span>
            <span class="meta-sep">·</span>
            <span class="meta-item">{{ t('Hits') }} <strong>{{ memory.hit_count }}</strong></span>
            <template v-if="memory.last_hit_at">
              <span class="meta-sep">·</span>
              <span class="meta-item">{{ fmtDateTime(memory.last_hit_at) }}</span>
            </template>
          </div>
          <details class="meta-ids">
            <summary class="meta-ids-toggle">IDs</summary>
            <div class="meta-ids-body">
              <span class="meta-item">
                ID: <code class="copyable" @click.stop="copy(memory.id)" :title="t('Click to copy')">{{ memory.id }}</code>
                <span class="copy-hint" v-if="copied === memory.id">{{ t('Copied') }}</span>
              </span>
              <span class="meta-sep">·</span>
              <span class="meta-item">
                Project: <code class="copyable" @click.stop="copy(memory.project_id)" :title="t('Click to copy')">{{ memory.project_id }}</code>
                <span class="copy-hint" v-if="copied === memory.project_id">{{ t('Copied') }}</span>
              </span>
            </div>
          </details>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style>
.detail-modal {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  width: 60vw; max-width: 60vw;
  max-height: 88vh;
  display: flex; flex-direction: column;
  box-shadow: 0 24px 70px var(--shadow), 0 0 0 1px rgba(0,212,138,0.06), 0 0 40px -28px var(--glow);
  animation: modal-in 200ms cubic-bezier(0.16, 1, 0.3, 1);
  overflow: hidden;
}
.detail-modal-body {
  flex: 1; overflow-y: auto;
  padding: 0 20px 20px;
}
.btn-header-edit {
  background: transparent; color: var(--text-muted);
  border: none; border-radius: var(--radius-sm);
  padding: 4px; display: flex; align-items: center; justify-content: center;
  cursor: pointer;
  transition: color var(--transition), background var(--transition);
}
.btn-header-edit:hover { color: var(--accent); background: var(--accent-dim); }
</style>
