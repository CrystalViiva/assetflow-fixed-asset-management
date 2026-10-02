import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import {dirname, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import {defineConfig, loadEnv} from 'vite';

const configDirectory = dirname(fileURLToPath(import.meta.url));

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, configDirectory, '');
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': resolve(configDirectory, '.'),
      },
    },
    server: {
      proxy: {
        '/api/v1': { target: env.DJANGO_DEV_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      },
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modify—file watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
      // Disable file watching when DISABLE_HMR is true to save CPU during agent edits.
      watch: process.env.DISABLE_HMR === 'true' ? null : {},
    },
  };
});
