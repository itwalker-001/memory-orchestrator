<script setup>
import { ref, computed, watch, inject, onBeforeUnmount, nextTick } from 'vue'
import { renderMarkdown } from './markdown.js'
import { apiJSON, errText } from './api.js'
import BaseModal from './BaseModal.vue'
import MarkdownEditor from './MarkdownEditor.vue'
import { IconExpand, IconContract } from './icons.js'
import {
  NCard, NInput, NButton, NSpace, NText, NFormItem, NSelect,
  NRadioGroup, NRadioButton, NRate, NIcon,
} from 'naive-ui'

const TYPES = ['user', 'feedback', 'project', 'reference']

const t = inject('t', k => k)

const props = defineProps({
  show: { type: Boolean, default: false },
  memory: { type: Object, default: null },
  showProject: { type: Boolean, default: false },
  projects: { type: Array, default: () => [] },
  defaultProjectId: { type: String, default: '' },
})
const emit = defineEmits(['close', 'saved'])

const isEdit = computed(() => !!props.memory)
const title = computed(() => isEdit.value ? t('Edit Memory') : t('New Memory'))

const form = ref(defaultForm())
const isSaving = ref(false)
const error = ref('')

function defaultForm() {
  return {
    type: 'project',
    name: '',
    description: '',
    content: '',
    why: '',
    how_to_apply: '',
    importance: 3,
    project_id: props.defaultProjectId || '',
  }
}

watch(() => props.show, open => {
  if (!open) return
  error.value = ''
  if (props.memory) {
    form.value = {
      type: props.memory.type || 'project',
      name: props.memory.name || '',
      description: props.memory.description || '',
      content: props.memory.content || '',
      why: props.memory.why || '',
      how_to_apply: props.memory.how_to_apply || '',
      importance: props.memory.importance ?? 3,
      project_id: props.memory.project_id || props.defaultProjectId || '',
    }
  } else {
    form.value = defaultForm()
  }
})

const mdPreview = computed(() => renderMarkdown(form.value.content))

// ── Fullscreen Content editor ──
const contentFull = ref(false)
function toggleFull() { contentFull.value = !contentFull.value }
function onKey(e) { if (e.key === 'Escape' && contentFull.value) { contentFull.value = false; e.stopPropagation() } }
watch(contentFull, on => {
  if (on) window.addEventListener('keydown', onKey, true)
  else window.removeEventListener('keydown', onKey, true)
})
// Leaving the modal must not strand the page in fullscreen.
watch(() => props.show, open => { if (!open) contentFull.value = false })

// ── Synced scrolling between editor (left) and preview (right) ──
const mdEditorRef = ref(null)
const mdPreviewRef = ref(null)
let editorScroll = null
let lock = false

function syncFrom(src, dst) {
  if (lock || !src || !dst) return
  lock = true
  const range = src.scrollHeight - src.clientHeight
  const ratio = range > 0 ? src.scrollTop / range : 0
  dst.scrollTop = ratio * (dst.scrollHeight - dst.clientHeight)
  requestAnimationFrame(() => { lock = false })
}

function onEditorScroll() { syncFrom(editorScroll, mdPreviewRef.value) }
function onPreviewScroll() { syncFrom(mdPreviewRef.value, editorScroll) }

function bindSyncScroll() {
  editorScroll = mdEditorRef.value?.getScrollDOM?.() || null
  if (editorScroll) editorScroll.addEventListener('scroll', onEditorScroll, { passive: true })
  if (mdPreviewRef.value) mdPreviewRef.value.addEventListener('scroll', onPreviewScroll, { passive: true })
}

function unbindSyncScroll() {
  if (editorScroll) editorScroll.removeEventListener('scroll', onEditorScroll)
  if (mdPreviewRef.value) mdPreviewRef.value.removeEventListener('scroll', onPreviewScroll)
  editorScroll = null
}

watch(() => props.show, open => {
  if (open) nextTick(() => { unbindSyncScroll(); bindSyncScroll() })
  else unbindSyncScroll()
})

onBeforeUnmount(() => { unbindSyncScroll(); window.removeEventListener('keydown', onKey, true) })

const projectOptions = computed(() =>
  props.projects.map(p => ({ label: p.display_name || p.slug, value: p.slug || p.id })),
)

async function save() {
  if (!form.value.name || !form.value.content) return
  isSaving.value = true
  error.value = ''
  try {
    const payload = { ...form.value }
    payload.importance = Math.min(5, Math.max(1, payload.importance || 1))
    if (!payload.why) delete payload.why
    if (!payload.how_to_apply) delete payload.how_to_apply
    if (!props.showProject) delete payload.project_id

    let result
    if (isEdit.value) {
      result = await apiJSON(`/memories/${props.memory.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        skipErrorToast: true,
      })
    } else {
      if (!payload.project_id) delete payload.project_id
      result = await apiJSON('/memories', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        skipErrorToast: true,
      })
    }
    emit('saved', result)
  } catch (e) {
    error.value = errText(e)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <BaseModal :show="show" :mask-closable="true" @close="emit('close')">
    <n-card
      v-if="show"
      :title="title"
      closable
      :bordered="false"
      style="width:80vw;max-width:960px"
      @close="emit('close')"
    >
      <n-space vertical :size="14">
        <n-radio-group v-model:value="form.type" size="small">
          <n-radio-button v-for="tp in TYPES" :key="tp" :value="tp">{{ t(tp) }}</n-radio-button>
        </n-radio-group>

        <n-form-item :label="t('Name')" label-placement="top" :show-feedback="false">
          <n-input v-model:value="form.name" :placeholder="t('Short identifier…')" />
        </n-form-item>

        <n-form-item :label="t('Description')" label-placement="top" :show-feedback="false">
          <n-input v-model:value="form.description" :placeholder="t('One-line summary…')" />
        </n-form-item>

        <n-form-item :label="t('Content')" label-placement="top" :show-feedback="false">
          <template #label>
            <div class="md-label-row">
              <span>{{ t('Content') }}</span>
              <button type="button" class="md-full-btn" :title="contentFull ? t('Exit fullscreen') : t('Fullscreen')" @click="toggleFull">
                <n-icon :size="15"><IconContract v-if="contentFull" /><IconExpand v-else /></n-icon>
              </button>
            </div>
          </template>
          <div class="md-split-editor" :class="{ 'md-split-editor--full': contentFull }">
            <MarkdownEditor ref="mdEditorRef" v-model:value="form.content" class="md-split-input" placeholder="Markdown…" />
            <div ref="mdPreviewRef" class="md-split-preview">
              <div class="md-body" v-html="mdPreview"></div>
            </div>
            <button v-if="contentFull" type="button" class="md-full-exit" :title="t('Exit fullscreen')" @click="toggleFull">
              <n-icon :size="16"><IconContract /></n-icon>
            </button>
          </div>
        </n-form-item>

        <n-form-item :label="t('Why')" label-placement="top" :show-feedback="false">
          <n-input v-model:value="form.why" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" :placeholder="t('Reason or motivation…')" />
        </n-form-item>

        <n-form-item :label="t('How to Apply')" label-placement="top" :show-feedback="false">
          <n-input v-model:value="form.how_to_apply" type="textarea" :autosize="{ minRows: 2, maxRows: 6 }" :placeholder="t('When / how to use this…')" />
        </n-form-item>

        <n-space :size="14">
          <n-form-item :label="t('Importance')" label-placement="top" :show-feedback="false">
            <n-space align="center" :size="8">
              <n-rate v-model:value="form.importance" :count="5" :allow-half="false" />
              <n-text depth="3" style="font-size:12px">{{ form.importance || 1 }}/5</n-text>
            </n-space>
          </n-form-item>
          <n-form-item v-if="showProject" :label="t('Project')" label-placement="top" :show-feedback="false">
            <n-select v-model:value="form.project_id" :options="projectOptions" style="width:220px" />
          </n-form-item>
        </n-space>
      </n-space>

      <n-text v-if="error" type="error" style="display:block;margin-top:8px;font-size:12px">{{ error }}</n-text>

      <template #footer>
        <n-space justify="end">
          <n-button @click="emit('close')">{{ t('Cancel') }}</n-button>
          <n-button type="primary" :loading="isSaving" :disabled="!form.name || !form.content" @click="save">
            {{ t('Save') }}
          </n-button>
        </n-space>
      </template>
    </n-card>
  </BaseModal>
</template>

<style scoped>
.md-split-editor { display: grid; grid-template-columns: 1fr 1fr; height: 280px; border: 1px solid var(--n-border-color, #e0e0e6); border-radius: 6px; overflow: hidden; width: 100%; }
/* Fullscreen: lift the split editor out to cover the whole viewport. */
.md-split-editor--full {
  position: fixed;
  inset: 0;
  z-index: 5000;
  height: 100vh;
  border: none;
  border-radius: 0;
  background: var(--n-color, #fff);
}
.md-label-row { display: flex; align-items: center; justify-content: space-between; width: 100%; }
.md-full-btn, .md-full-exit {
  display: inline-flex; align-items: center; justify-content: center;
  border: none; background: transparent; cursor: pointer; padding: 2px;
  color: var(--n-text-color-3, #909399); border-radius: 4px;
  transition: background 0.15s ease, color 0.15s ease;
}
.md-full-btn:hover, .md-full-exit:hover { background: rgba(128,128,128,0.14); color: var(--n-text-color-1, #1f2225); }
/* Floating exit affordance inside the fullscreen overlay. */
.md-full-exit { position: absolute; top: 12px; right: 14px; z-index: 1; width: 30px; height: 30px; }
.md-split-input { min-width: 0; height: 100%; overflow: hidden; }
.md-split-input :deep(.cm-editor) { height: 100%; }
.md-split-preview { min-width: 0; height: 100%; overflow: auto; border-left: 1px solid var(--n-border-color, #e0e0e6); }
.md-split-preview .md-body { padding: 10px 16px; }
.md-body { font-size: 13px; line-height: 1.65; }
.md-body :deep(p) { margin: 4px 0; }
.md-body :deep(ul), .md-body :deep(ol) { margin: 4px 0; padding-left: 22px; }
.md-body :deep(ul) { list-style: disc; }
.md-body :deep(ol) { list-style: decimal; }
.md-body :deep(li) { margin: 2px 0; }
.md-body :deep(h1), .md-body :deep(h2), .md-body :deep(h3),
.md-body :deep(h4), .md-body :deep(h5), .md-body :deep(h6) { margin: 10px 0 4px; font-weight: 700; line-height: 1.3; }
.md-body :deep(blockquote) { margin: 6px 0; padding-left: 10px; border-left: 3px solid var(--n-border-color, rgba(128,128,128,0.3)); opacity: 0.85; }
.md-body :deep(a) { color: #18a058; text-decoration: none; }
.md-body :deep(a:hover) { text-decoration: underline; }
.md-body :deep(table) { border-collapse: collapse; margin: 6px 0; }
.md-body :deep(th), .md-body :deep(td) { border: 1px solid var(--n-border-color, rgba(128,128,128,0.3)); padding: 4px 8px; }
.md-body :deep(pre) { padding: 10px; border-radius: 6px; overflow-x: auto; font-size: 12px; }
.md-body :deep(code) { font-family: 'FiraCode', monospace; font-size: 12px; }
</style>
