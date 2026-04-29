import { defineConfig } from 'vite'
import preact from '@preact/preset-vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [preact(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:7860' },
      '/ws':  { target: 'ws://127.0.0.1:7860', ws: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
