import path from 'node:path'
import fs from 'node:fs'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { defineConfig, type Plugin } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

function buildFingerprint(): Plugin {
  const SRC_EXTS = new Set(['.vue', '.ts', '.js', '.css', '.json', '.html'])

  return {
    name: 'build-fingerprint',
    apply: 'build',
    closeBundle() {
      const srcDir = path.resolve(__dirname, 'src')
      const distDir = path.resolve(__dirname, 'dist')
      const hasher = crypto.createHash('sha256')

      function walk(dir: string) {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
          const full = path.join(dir, entry.name)
          if (entry.isDirectory()) {
            walk(full)
          } else if (entry.isFile() && SRC_EXTS.has(path.extname(entry.name))) {
            hasher.update(path.relative(srcDir, full))
            hasher.update(fs.readFileSync(full))
          }
        }
      }

      walk(srcDir)
      fs.writeFileSync(path.join(distDir, '.build_fingerprint'), hasher.digest('hex'))
    },
  }
}

export default defineConfig({
  plugins: [vue(), tailwindcss(), buildFingerprint()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
})
