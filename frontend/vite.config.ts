import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus')) return 'element-ui'
          if (id.includes('node_modules/vue') || id.includes('node_modules/@vue')) return 'vue-runtime'
          if (id.includes('node_modules/axios')) return 'http-client'
        },
      },
    },
  },
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8000' },
  },
})
