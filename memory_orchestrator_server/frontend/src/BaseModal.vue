<script setup>
// Thin wrapper over Naive UI's NModal that preserves the project's hand-built
// modal cards. Each call site keeps its own inner card markup as the default
// slot; this component only supplies the backdrop, centering, focus trap, ESC
// and click-outside behavior (previously hand-rolled via .modal-overlay).
import { NModal } from 'naive-ui'

defineProps({
  // Whether the modal is visible. Mounting is gated on this (v-if) so the
  // default slot is never evaluated while closed — avoids NModal's
  // "default slot is empty" warning and lets slots reference a possibly-null
  // target object without guards.
  show: { type: Boolean, default: false },
  // Allow closing by clicking the backdrop. Off by default — opt in per modal
  // to match the old @click.self behavior (confirm dialogs stay sticky).
  maskClosable: { type: Boolean, default: false },
})

const emit = defineEmits(['close'])
</script>

<template>
  <n-modal
    v-if="show"
    :show="true"
    :mask-closable="maskClosable"
    :auto-focus="false"
    transform-origin="center"
    @update:show="v => { if (!v) emit('close') }"
  >
    <slot />
  </n-modal>
</template>
