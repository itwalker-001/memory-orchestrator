<template>
  <n-config-provider :theme="naiveTheme" :theme-overrides="themeOverrides">
    <n-message-provider>
      <n-dialog-provider>
        <ApiBridge />
        <RouterView />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>

<script setup>
import { computed, defineComponent, onMounted } from 'vue'
import { NConfigProvider, NMessageProvider, NDialogProvider, darkTheme, useMessage } from 'naive-ui'
import { storeToRefs } from 'pinia'
import { useAppStore } from './stores/app.js'
import { setApiHandlers } from './api.js'

const appStore = useAppStore()
const { isDark } = storeToRefs(appStore)
const naiveTheme = computed(() => (isDark.value ? darkTheme : null))

// useMessage() must run under <n-message-provider>, so wire the api handlers from
// this inner component that lives inside the provider tree.
const ApiBridge = defineComponent({
  name: 'ApiBridge',
  setup() {
    const message = useMessage()
    // Register after mount so the n-message-provider is fully initialized; wiring
    // during synchronous setup can capture a message instance whose container is
    // not yet attached, making message.error() a silent no-op.
    onMounted(() => {
      setApiHandlers({
        onError: msg => message.error(msg),
        on401: () => { appStore.loginOpen = true },
      })
    })
    return () => null
  },
})

// Purple accent for dark mode only; light mode keeps Naive UI defaults.
const darkPurple = {
  common: {
    primaryColor: '#a87ffb',
    primaryColorHover: '#b794fc',
    primaryColorPressed: '#8b5cf6',
    primaryColorSuppl: '#a87ffb',
  },
}
const themeOverrides = computed(() => (isDark.value ? darkPurple : null))
</script>
