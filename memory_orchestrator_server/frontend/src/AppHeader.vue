<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NSpace, NText, NIcon } from 'naive-ui'
import { useAppStore } from './stores/app.js'
import {
  IconDatabase, IconFolder, IconLock, IconLogout, IconMoon, IconSettings,
  IconSun, IconInfo,
} from './icons.js'
import BrandLogo from './BrandLogo.vue'

const props = defineProps({
  loginOpen: { type: Boolean, default: false },
})

const emit = defineEmits(['logout'])

const router = useRouter()
const route = useRoute()
const app = useAppStore()
const { isDark, lang, t, toggleTheme, toggleLang } = app

const navOptions = computed(() => [
  { label: t('Projects'), key: '/', iconComponent: IconFolder },
  { label: t('Memories'), key: '/memories', iconComponent: IconDatabase },
  { label: t('Tokens'), key: '/tokens', iconComponent: IconLock },
])

function openNav(key) {
  if (key !== route.path) router.push(key)
}

function openInNewTab(path) {
  window.open(router.resolve(path).href, '_blank')
}
</script>

<template>
  <header class="app-header">
    <div class="logo">
      <BrandLogo :size="20" />
      <n-text strong style="font-size:14px;white-space:nowrap">Memory Orchestrator</n-text>
      <span v-if="app.version" class="version-badge">v{{ app.version }}</span>
    </div>

    <nav class="header-nav">
      <n-button
        v-for="opt in navOptions"
        :key="opt.key"
        quaternary
        size="small"
        class="nav-item"
        :type="route.path === opt.key ? 'primary' : 'default'"
        @click="openNav(opt.key)"
      >
        <template #icon><n-icon><component :is="opt.iconComponent" /></n-icon></template>
        {{ opt.label }}
      </n-button>
      <slot name="nav" />
    </nav>

    <div class="header-spacer" />

    <n-space :size="6" align="center">
      <n-button quaternary circle @click="toggleTheme" :title="isDark ? t('Switch to light') : t('Switch to dark')">
        <template #icon><n-icon><IconSun v-if="isDark" /><IconMoon v-else /></n-icon></template>
      </n-button>

      <n-button quaternary circle @click="toggleLang" :title="lang === 'en' ? '切换中文' : 'Switch to English'">
        <span style="font-size:11px;font-weight:600">{{ lang === 'en' ? '中' : 'EN' }}</span>
      </n-button>

      <n-button v-if="!loginOpen" quaternary circle @click="openInNewTab('/help')" :title="t('Help')">
        <template #icon><n-icon><IconInfo /></n-icon></template>
      </n-button>

      <n-button v-if="!loginOpen" quaternary circle @click="openInNewTab('/settings')" :title="t('Settings')">
        <template #icon><n-icon><IconSettings /></n-icon></template>
      </n-button>

      <n-button v-if="!loginOpen" quaternary circle type="error" @click="emit('logout')" :title="t('Logout')">
        <template #icon><n-icon><IconLogout /></n-icon></template>
      </n-button>
    </n-space>
  </header>
</template>

<style scoped>
.app-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 12px;
}
.logo { display: flex; align-items: center; gap: 8px; }
.version-badge {
  font-size: 11px;
  font-weight: 500;
  color: var(--n-text-color-disabled, #9ca3af);
  opacity: 0.65;
  letter-spacing: 0.02em;
}
.header-nav { display: flex; align-items: center; gap: 4px; }
.header-nav :deep(a) { font-size: 13px; text-decoration: none; color: inherit; opacity: 0.7; }
.header-nav :deep(a:hover) { opacity: 1; text-decoration: underline; }
.nav-item { font-size: 13px; }
.header-spacer { flex: 1; }
</style>
