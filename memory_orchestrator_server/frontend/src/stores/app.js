import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import en from '../locales/en.json'
import zh from '../locales/zh.json'

const _locales = { en, zh }

export const useAppStore = defineStore('app', () => {
  // ── Theme ──────────────────────────────────────────────────────────────────
  const stored = localStorage.getItem('mo-theme')
  const isDark = ref(stored ? stored === 'dark' : window.matchMedia('(prefers-color-scheme: dark)').matches)

  function applyTheme(dark) {
    document.documentElement.setAttribute('data-theme', dark ? 'dark' : 'light')
  }
  applyTheme(isDark.value)

  watch(isDark, v => {
    localStorage.setItem('mo-theme', v ? 'dark' : 'light')
    applyTheme(v)
  })

  function toggleTheme() { isDark.value = !isDark.value }

  // ── Language ───────────────────────────────────────────────────────────────
  const lang = ref(localStorage.getItem('mo-lang') || 'en')

  watch(lang, v => localStorage.setItem('mo-lang', v))

  function toggleLang() { lang.value = lang.value === 'en' ? 'zh' : 'en' }

  function t(key, vars) {
    const locale = _locales[lang.value] || _locales.en
    const str = locale[key] ?? key
    if (!vars) return str
    return str.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''))
  }

  // ── Auth ───────────────────────────────────────────────────────────────────
  const loginOpen = ref(false)
  const loginInput = ref('')
  const loginError = ref('')
  const loginLoading = ref(false)

  async function submitLogin(BASE) {
    loginLoading.value = true; loginError.value = ''
    try {
      const r = await fetch(`${BASE}/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: loginInput.value }),
      })
      if (r.status === 401) { loginError.value = t('Invalid token'); return false }
      loginOpen.value = false; loginInput.value = ''
      return true
    } catch (e) { loginError.value = e.message; return false }
    finally { loginLoading.value = false }
  }

  async function skipLogin(BASE) {
    loginLoading.value = true
    try {
      const r = await fetch(`${BASE}/login`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: '' }),
      })
      if (r.status === 401) { loginError.value = t('Server requires a token'); return false }
      loginOpen.value = false; return true
    } finally { loginLoading.value = false }
  }

  async function logout(BASE) {
    await fetch(`${BASE}/logout`, { method: 'POST' })
    loginOpen.value = true
  }

  return {
    isDark, toggleTheme,
    lang, toggleLang, t,
    loginOpen, loginInput, loginError, loginLoading,
    submitLogin, skipLogin, logout,
  }
})
