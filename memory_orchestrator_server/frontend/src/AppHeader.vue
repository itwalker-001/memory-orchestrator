<script setup>
import { computed, h } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { NButton, NSpace, NText, NIcon, NDropdown } from 'naive-ui'
import { useAppStore } from './stores/app.js'
import {
  IconDatabase, IconFolder, IconLock, IconLogout, IconMoon, IconSettings,
  IconSun,
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

function navIcon(icon) {
  return () => h(NIcon, null, { default: () => h(icon) })
}

const navOptions = computed(() => [
  { label: t('Projects'), key: '/', icon: navIcon(IconFolder), disabled: route.path === '/' },
  { label: t('Memories'), key: '/memories', icon: navIcon(IconDatabase), disabled: route.path === '/memories' },
  { label: t('Tokens'), key: '/tokens', icon: navIcon(IconLock), disabled: route.path === '/tokens' },
])

const currentNavLabel = computed(() => {
  const active = navOptions.value.find(option => option.key === route.path)
  return active?.label || t('Projects')
})

function openNav(key) {
  if (key !== route.path) router.push(key)
}
</script>

<template>
  <header class="app-header">
    <div class="logo">
      <BrandLogo :size="20" />
      <n-text strong style="font-size:14px;white-space:nowrap">Memory Orchestrator</n-text>
    </div>

    <nav class="header-nav">
      <n-dropdown trigger="hover" :options="navOptions" @select="openNav">
        <n-button quaternary size="small" class="nav-trigger">
          {{ currentNavLabel }}
        </n-button>
      </n-dropdown>
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

      <n-button v-if="!loginOpen" quaternary circle @click="router.push('/settings')" :title="t('Settings')">
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
.header-nav { display: flex; align-items: center; gap: 12px; }
.header-nav :deep(a) { font-size: 13px; text-decoration: none; color: inherit; opacity: 0.7; }
.header-nav :deep(a:hover) { opacity: 1; text-decoration: underline; }
.nav-trigger { font-size: 13px; }
.header-spacer { flex: 1; }
</style>
