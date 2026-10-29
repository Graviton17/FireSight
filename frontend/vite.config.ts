import path from 'node:path'
import react, { reactCompilerPreset } from '@vitejs/plugin-react'
import babel from '@rolldown/plugin-babel'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    babel({ presets: [reactCompilerPreset()] }),
    tailwindcss(),
  ],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: {
    // The backend (backend/main.py) listens on :8000; FIRESIGHT_API_URL overrides.
    proxy: { '/api': process.env.FIRESIGHT_API_URL ?? 'http://localhost:8000' },
  },
})
