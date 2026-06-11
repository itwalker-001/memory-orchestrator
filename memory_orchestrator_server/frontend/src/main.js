import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import { createPinia } from 'pinia'
import 'vfonts/Lato.css'
import 'vfonts/FiraCode.css'
import './style.css'
import App from './App.vue'
import { initMarkdown } from './markdown.js'
import MemoriesPage from './MemoriesPage.vue'
import SkeletonPage from './SkeletonPage.vue'
import SettingsPage from './SettingsPage.vue'
import HelpPage from './HelpPage.vue'
import TokensPage from './TokensPage.vue'

const router = createRouter({
  history: createWebHistory('/ui/'),
  routes: [
    { path: '/', component: SkeletonPage },
    { path: '/memories', component: MemoriesPage },
    { path: '/settings', component: SettingsPage },
    { path: '/help', component: HelpPage },
    { path: '/tokens', component: TokensPage },
  ],
})

// Preload the Shiki highlighter before mount so renderMarkdown stays synchronous.
await initMarkdown()

createApp(App)
  .use(createPinia())
  .use(router)
  .mount('#app')
