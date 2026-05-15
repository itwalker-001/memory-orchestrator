<script setup>
import { useRouter } from 'vue-router'
import { useAppStore } from './stores/app.js'
import IconSun from './icons/IconSun.svg'
import IconMoon from './icons/IconMoon.svg'
import IconSettings from './icons/IconSettings.svg'
import IconLock from './icons/IconLock.svg'
import IconLogout from './icons/IconLogout.svg'
import logoUrl from './assets/logo.svg?url'

const props = defineProps({
  loginOpen: { type: Boolean, default: false },
})

const emit = defineEmits(['open-settings', 'logout'])

const router = useRouter()
const app = useAppStore()
const { isDark, lang, t, toggleTheme, toggleLang } = app
</script>

<template>
  <header class="app-header">
    <div class="logo">
      <img :src="logoUrl" width="18" height="18" alt="Memory Orchestrator logo" />
      <h1>Memory Orchestrator</h1>
    </div>

    <nav class="header-nav">
      <slot name="nav" />
    </nav>

    <div class="header-spacer" />

    <div class="header-actions">
      <button @click="toggleTheme" class="btn-theme"
        :title="isDark ? t('Switch to light') : t('Switch to dark')">
        <IconSun v-if="isDark" width="14" height="14" />
        <IconMoon v-else width="14" height="14" />
      </button>

      <button @click="toggleLang" class="btn-theme"
        :title="lang === 'en' ? '切换中文' : 'Switch to English'">
        <span style="font-size:11px;font-weight:600;letter-spacing:0">{{ lang === 'en' ? '中' : 'EN' }}</span>
      </button>

      <button @click="emit('open-settings')" class="btn-theme" :title="t('Settings')" v-if="!loginOpen">
        <IconSettings width="14" height="14" />
      </button>

      <button v-if="!loginOpen" @click="router.push('/tokens')" class="btn-theme btn-admin" :title="t('Admin')">
        <IconLock width="14" height="14" />
      </button>

      <button v-if="!loginOpen" @click="emit('logout')" class="btn-theme btn-logout" :title="t('Logout')">
        <IconLogout width="14" height="14" />
      </button>

    </div>
  </header>
</template>

<style scoped>
.app-header {
  display: flex; align-items: center; gap: 12px;
  padding: 8px 10px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-lg);
  background: var(--surface-panel);
  box-shadow: 0 10px 32px -28px var(--shadow), inset 0 1px 0 rgba(255,255,255,0.08);
  backdrop-filter: blur(12px);
}
[data-theme="dark"] .app-header {
  border-color: rgba(0,212,138,0.20);
  box-shadow: 0 0 0 1px rgba(0,212,138,0.06), 0 8px 32px -16px rgba(0,0,0,0.9), inset 0 1px 0 rgba(0,212,138,0.05);
}
.logo { display: flex; align-items: center; gap: 8px; }
.logo h1 {
  font-family: 'Orbitron', ui-monospace, SFMono-Regular, monospace;
  font-size: 12px; font-weight: 700; color: var(--text-primary);
  letter-spacing: 0.10em; text-transform: uppercase; margin: 0;
}
[data-theme="dark"] .logo h1 { color: var(--accent); text-shadow: 0 0 14px rgba(0,212,138,0.45); }
.header-nav { display: flex; align-items: center; gap: 12px; }
.header-nav :deep(a) { font-size: 12px; color: var(--accent, #2563eb); text-decoration: none; }
.header-nav :deep(a:hover) { text-decoration: underline; }
.header-spacer { flex: 1; }
.header-actions { display: flex; align-items: center; gap: 8px; }
.btn-theme {
  display: flex; align-items: center; justify-content: center;
  width: 30px; height: 30px;
  background: var(--surface-panel); color: var(--text-secondary);
  border: 1px solid var(--border); border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition), color var(--transition), border-color var(--transition), box-shadow var(--transition);
}
.btn-theme:hover { background: var(--surface-2); color: var(--accent); border-color: var(--border-hover); box-shadow: 0 0 0 3px var(--accent-dim); }
.btn-theme:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.btn-logout { color: var(--text-muted); }
.btn-logout:hover { color: var(--red) !important; }
.btn-admin { text-decoration: none; display: inline-flex; align-items: center; justify-content: center; }
@keyframes spin { to { transform: rotate(360deg); } }
.spinning { animation: spin 0.7s linear infinite; }
</style>
