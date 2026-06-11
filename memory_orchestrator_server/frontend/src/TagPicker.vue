<!-- frontend/src/TagPicker.vue -->
<template>
  <n-select
    multiple
    filterable
    tag
    clearable
    size="small"
    :value="modelValue"
    :options="options"
    :placeholder="t('Search or create tag…')"
    @update:value="onUpdate"
  />
</template>

<script setup>
import { computed, inject } from 'vue'
import { NSelect } from 'naive-ui'

const t = inject('t', k => k)

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  allTags: { type: Array, default: () => [] },
})
const emit = defineEmits(['update:modelValue'])

const options = computed(() => {
  const set = new Set([...(props.allTags || []), ...(props.modelValue || [])])
  return [...set].map(tag => ({ label: tag, value: tag }))
})

function onUpdate(values) {
  const clean = [...new Set((values || []).map(v => String(v).trim().replace(/^#/, '')).filter(Boolean))]
  emit('update:modelValue', clean)
}
</script>
