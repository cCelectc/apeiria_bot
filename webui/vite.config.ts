import { defineConfig } from 'vite'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'

// https://vite.dev/config/
export default defineConfig({
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes('node_modules')) {
            return undefined
          }
          if (id.includes('monaco-editor/esm/vs/editor/')) {
            return 'monaco-editor'
          }
          if (id.includes('monaco-editor/esm/vs/base/')) {
            return 'monaco-base'
          }
          if (id.includes('monaco-editor/esm/vs/platform/')) {
            return 'monaco-platform'
          }
          if (id.includes('monaco-editor/esm/vs/')) {
            return 'monaco-vs'
          }
          if (id.includes('/vue/') || id.includes('/vue-router/') || id.includes('/pinia/')) {
            return 'framework'
          }
          return undefined
        },
      },
    },
  },
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
