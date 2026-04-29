import path from 'node:path'
import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

const preactCompat = path.resolve(__dirname, 'node_modules/preact/compat')

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
      server: {
        deps: {
          inline: ['@tanstack/react-table', '@tanstack/table-core'],
        },
      },
    },
    resolve: {
      alias: {
        react: preactCompat,
        'react-dom': preactCompat,
        'react/jsx-runtime': preactCompat,
      },
    },
  }),
)
