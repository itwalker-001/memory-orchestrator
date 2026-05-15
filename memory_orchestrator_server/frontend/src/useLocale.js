import { ref } from 'vue'
import en from './locales/en.json'
import zh from './locales/zh.json'

const _locales = { en, zh }
const lang = ref(localStorage.getItem('mo-lang') || 'en')

export function useLocale() {
  function t(key, vars) {
    const locale = _locales[lang.value] || _locales.en
    const str = locale[key] ?? key
    if (!vars) return str
    return str.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? ''))
  }
  function toggleLang() {
    lang.value = lang.value === 'en' ? 'zh' : 'en'
    localStorage.setItem('mo-lang', lang.value)
  }
  return { lang, t, toggleLang }
}
