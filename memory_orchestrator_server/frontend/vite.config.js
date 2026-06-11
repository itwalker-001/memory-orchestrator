import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import svgLoader from 'vite-svg-loader'

export default defineConfig({
  plugins: [vue(), svgLoader({ defaultImport: 'component' })],
  base: '/ui/',
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://172.16.10.123:8765', changeOrigin: true }
    }
  },
  build: { outDir: 'dist' }
})
