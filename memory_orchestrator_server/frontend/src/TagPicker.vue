<!-- frontend/src/TagPicker.vue -->
<template>
  <div class="tag-picker">
    <div class="tag-chips">
      <span v-for="tag in modelValue" :key="tag" class="tag-chip">
        {{ tag }}
        <button class="chip-rm" @click="removeTag(tag)">×</button>
      </span>
    </div>
    <div class="tag-input-wrap">
      <input
        ref="inputEl"
        v-model="query"
        class="tag-input"
        :placeholder="t('Search or create tag…')"
        @input="onInput"
        @keydown.enter.prevent="selectFirst"
        @keydown.escape="query = ''"
        @focus="showSuggestions = true"
        @blur="onBlur"
      />
    </div>
    <ul v-if="showSuggestions && (suggestions.length || query)" class="tag-suggestions">
      <li
        v-for="s in suggestions"
        :key="s"
        class="tag-sug"
        @mousedown.prevent="addTag(s)"
        v-html="highlight(s)"
      ></li>
      <li
        v-if="query && !suggestions.includes(query)"
        class="tag-create"
        @mousedown.prevent="addTag(query)"
      >
        {{ t('+ Create "{tag}"', { tag: query }) }}
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, computed, inject } from 'vue'

const t = inject('t', k => k)

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const query = ref('')
const showSuggestions = ref(false)
const inputEl = ref(null)

const suggestions = computed(() => {
  if (!query.value) return props.allTags.filter(t => !props.modelValue.includes(t)).slice(0, 8)
  const q = query.value.toLowerCase()
  return props.allTags.filter(t => t.toLowerCase().includes(q) && !props.modelValue.includes(t)).slice(0, 8)
})

function highlight(tag) {
  if (!query.value) return tag
  const idx = tag.toLowerCase().indexOf(query.value.toLowerCase())
  if (idx === -1) return tag
  return tag.slice(0, idx) + '<mark>' + tag.slice(idx, idx + query.value.length) + '</mark>' + tag.slice(idx + query.value.length)
}

function addTag(tag) {
  const clean = tag.trim().replace(/^#/, '')
  if (!clean || props.modelValue.includes(clean)) return
  emit('update:modelValue', [...props.modelValue, clean])
  query.value = ''
  showSuggestions.value = false
}

function removeTag(tag) {
  emit('update:modelValue', props.modelValue.filter(t => t !== tag))
}

function selectFirst() {
  if (suggestions.value.length) addTag(suggestions.value[0])
  else if (query.value) addTag(query.value)
}

function onInput() { showSuggestions.value = true }
function onBlur() { setTimeout(() => { showSuggestions.value = false }, 150) }
</script>

<style scoped>
.tag-picker { display: flex; flex-direction: column; gap: 6px; }
.tag-chips { display: flex; flex-wrap: wrap; gap: 4px; min-height: 20px; }
.tag-chip {
  display: inline-flex; align-items: center; gap: 3px;
  background: var(--tag-bg, #1a3a52); color: var(--accent, #58a6ff);
  border-radius: 10px; font-size: 10px; padding: 2px 8px;
  border: 1px solid var(--accent-dim, #1f6feb44);
}
.chip-rm { background: none; border: none; color: var(--fg-muted, #6e7681); cursor: pointer; font-size: 11px; padding: 0; line-height: 1; }
.chip-rm:hover { color: #ff7b72; }
.tag-input-wrap { position: relative; }
.tag-input {
  width: 100%; background: var(--input-bg, #0d1117); border: 1px solid var(--border, #30363d);
  border-radius: 5px; padding: 5px 8px; font-size: 11px; color: var(--fg, #c9d1d9);
  font-family: inherit; outline: none;
}
.tag-input:focus { border-color: var(--accent, #58a6ff); }
.tag-suggestions {
  list-style: none; padding: 4px; margin: 0;
  background: var(--tooltip-bg, #161b22); border: 1px solid var(--border, #30363d);
  border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.4);
}
.tag-sug, .tag-create {
  padding: 5px 8px; font-size: 11px; border-radius: 4px; cursor: pointer;
  color: var(--fg, #c9d1d9);
}
.tag-sug:hover, .tag-create:hover { background: var(--btn-bg, #21262d); }
.tag-create { color: #3fb950; }
.tag-sug :deep(mark) { background: transparent; color: var(--accent, #58a6ff); font-style: normal; }
</style>
