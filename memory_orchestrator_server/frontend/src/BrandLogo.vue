<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useAppStore } from './stores/app.js'

defineProps({ size: { type: Number, default: 20 } })

const { isDark } = storeToRefs(useAppStore())
const brand = computed(() => (isDark.value ? '#a87ffb' : '#18a058'))
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Memory Orchestrator logo">
    <rect x="1" y="1" width="30" height="30" rx="7" :fill="brand" />
    <path d="M8 11.5H12.2L15.5 8.5H20.5" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M8 20.5H12.2L15.5 23.5H24" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
    <path d="M11 16H21" stroke="#fff" stroke-width="2" stroke-linecap="round" opacity="0.85" />
    <path d="M20.5 8.5L24 12V20.5" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" opacity="0.85" />
    <circle cx="8" cy="11.5" r="2" fill="#fff" />
    <circle cx="8" cy="20.5" r="2" fill="#fff" />
    <circle cx="11" cy="16" r="2.3" fill="#fff" />
    <circle cx="21" cy="16" r="2.3" fill="#fff" />
    <circle cx="24" cy="12" r="2" fill="#fff" />
    <circle cx="24" cy="20.5" r="2" fill="#fff" />
  </svg>
</template>
