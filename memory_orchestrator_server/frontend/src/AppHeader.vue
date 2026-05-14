<script setup>
import { computed } from 'vue'
import enLocale from './locales/en.json'
import zhLocale from './locales/zh.json'

const props = defineProps({
  isDark:    { type: Boolean, default: false },
  lang:      { type: String,  default: 'en' },
  loginOpen: { type: Boolean, default: false },
})

const emit = defineEmits(['toggle-theme', 'toggle-lang', 'open-settings', 'open-admin', 'logout'])

const _locales = { en: enLocale, zh: zhLocale }
function t(key) { return (_locales[props.lang] || _locales.en)[key] ?? key }
</script>

<template>
  <header class="app-header">
    <div class="logo">
      <svg width="18" height="18" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="mo-logo-bg" x1="4" y1="3" x2="28" y2="29" gradientUnits="userSpaceOnUse">
            <stop stop-color="#0f172a"/><stop offset="1" stop-color="#1d4ed8"/>
          </linearGradient>
          <linearGradient id="mo-logo-line" x1="8" y1="8" x2="24" y2="24" gradientUnits="userSpaceOnUse">
            <stop stop-color="#67e8f9"/><stop offset="1" stop-color="#a7f3d0"/>
          </linearGradient>
        </defs>
        <rect x="1" y="1" width="30" height="30" rx="7" fill="url(#mo-logo-bg)"/>
        <path d="M8 11.5H12.2L15.5 8.5H20.5" stroke="url(#mo-logo-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M8 20.5H12.2L15.5 23.5H24" stroke="url(#mo-logo-line)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <path d="M11 16H21" stroke="#93c5fd" stroke-width="2" stroke-linecap="round"/>
        <path d="M20.5 8.5L24 12V20.5" stroke="#60a5fa" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="8" cy="11.5" r="2" fill="#22d3ee"/>
        <circle cx="8" cy="20.5" r="2" fill="#22d3ee"/>
        <circle cx="11" cy="16" r="2.3" fill="#bfdbfe"/>
        <circle cx="21" cy="16" r="2.3" fill="#bfdbfe"/>
        <circle cx="24" cy="12" r="2" fill="#34d399"/>
        <circle cx="24" cy="20.5" r="2" fill="#34d399"/>
      </svg>
      <h1>Memory Orchestrator</h1>
    </div>

    <nav class="header-nav">
      <slot name="nav" />
    </nav>

    <div class="header-spacer" />

    <div class="header-actions">
      <button @click="emit('toggle-theme')" class="btn-theme"
        :title="isDark ? t('Switch to light') : t('Switch to dark')">
        <svg v-if="isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <circle cx="12" cy="12" r="4"/>
          <line x1="12" y1="2" x2="12" y2="5"/><line x1="12" y1="19" x2="12" y2="22"/>
          <line x1="4.22" y1="4.22" x2="6.34" y2="6.34"/><line x1="17.66" y1="17.66" x2="19.78" y2="19.78"/>
          <line x1="2" y1="12" x2="5" y2="12"/><line x1="19" y1="12" x2="22" y2="12"/>
          <line x1="4.22" y1="19.78" x2="6.34" y2="17.66"/><line x1="17.66" y1="6.34" x2="19.78" y2="4.22"/>
        </svg>
        <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      </button>

      <button @click="emit('toggle-lang')" class="btn-theme"
        :title="lang === 'en' ? '切换中文' : 'Switch to English'">
        <span style="font-size:11px;font-weight:600;letter-spacing:0">{{ lang === 'en' ? '中' : 'EN' }}</span>
      </button>

      <button @click="emit('open-settings')" class="btn-theme" :title="t('Settings')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"/>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
        </svg>
      </button>

      <button v-if="!loginOpen" @click="emit('open-admin')" class="btn-theme btn-admin" :title="t('Admin')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>
        </svg>
      </button>

      <button v-if="!loginOpen" @click="emit('logout')" class="btn-theme btn-logout" :title="t('Logout')">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
          <polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>
        </svg>
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
