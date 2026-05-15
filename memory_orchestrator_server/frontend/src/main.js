import { createApp, h } from 'vue'
import { createRouter, createWebHistory, RouterView } from 'vue-router'
import '@fontsource/orbitron/700.css'
import '@fontsource/orbitron/900.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
import './style.css'
import App from './App.vue'
import SkeletonPage from './SkeletonPage.vue'
import SettingsPage from './SettingsPage.vue'
import TokensPage from './TokensPage.vue'

const router = createRouter({
  history: createWebHistory('/ui/'),
  routes: [
    { path: '/', component: SkeletonPage },
    { path: '/memories', component: App },
    { path: '/settings', component: SettingsPage },
    { path: '/tokens', component: TokensPage },
  ],
})

createApp({ render: () => h(RouterView) })
  .use(router)
  .mount('#app')
