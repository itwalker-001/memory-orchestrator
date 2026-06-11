<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { storeToRefs } from 'pinia'
import { EditorView, keymap, lineNumbers, placeholder as cmPlaceholder } from '@codemirror/view'
import { EditorState, Compartment } from '@codemirror/state'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import { languages } from '@codemirror/language-data'
import { oneDark } from '@codemirror/theme-one-dark'
import { useAppStore } from './stores/app.js'

const props = defineProps({
  value: { type: String, default: '' },
  placeholder: { type: String, default: 'Markdown…' },
  minHeight: { type: String, default: '240px' },
})
const emit = defineEmits(['update:value'])

const { isDark } = storeToRefs(useAppStore())

const host = ref(null)
let view = null
const themeComp = new Compartment()

// Base look: monospace, FiraCode, sized to match the old textarea, wrapped lines.
const baseTheme = EditorView.theme({
  '&': { fontSize: '12.5px' },
  '.cm-content': { fontFamily: "'FiraCode', monospace", lineHeight: '1.6' },
  '.cm-gutters': { fontFamily: "'FiraCode', monospace" },
  '.cm-scroller': { overflow: 'auto' },
})

function themeExt(dark) {
  return dark ? oneDark : []
}

onMounted(() => {
  const state = EditorState.create({
    doc: props.value || '',
    extensions: [
      lineNumbers(),
      history(),
      keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
      markdown({ codeLanguages: languages }),
      EditorView.lineWrapping,
      cmPlaceholder(props.placeholder),
      baseTheme,
      themeComp.of(themeExt(isDark.value)),
      EditorView.updateListener.of(u => {
        if (u.docChanged) {
          const doc = u.state.doc.toString()
          if (doc !== props.value) emit('update:value', doc)
        }
      }),
    ],
  })
  view = new EditorView({ state, parent: host.value })
})

// External value → editor (e.g. modal opens and injects form.content).
watch(() => props.value, val => {
  if (!view) return
  const cur = view.state.doc.toString()
  if (val !== cur) {
    view.dispatch({ changes: { from: 0, to: cur.length, insert: val || '' } })
  }
})

// Theme follow.
watch(isDark, dark => {
  if (!view) return
  view.dispatch({ effects: themeComp.reconfigure(themeExt(dark)) })
})

onBeforeUnmount(() => { view?.destroy(); view = null })

// Expose the CM scroll container so a parent can sync-scroll a preview pane.
defineExpose({
  getScrollDOM: () => view?.scrollDOM || null,
})
</script>

<template>
  <div ref="host" class="md-editor" :style="{ minHeight }"></div>
</template>

<style scoped>
.md-editor { width: 100%; }
.md-editor :deep(.cm-editor) { height: 100%; }
.md-editor :deep(.cm-editor.cm-focused) { outline: none; }
.md-editor :deep(.cm-scroller) { min-height: inherit; }
</style>
