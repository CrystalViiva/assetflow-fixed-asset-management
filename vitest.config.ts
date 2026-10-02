import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: { environment: 'jsdom', include: ['src/**/*.test.{ts,tsx}'], setupFiles: ['src/test/setup.ts'],
    env: { VITE_DATA_SOURCE: 'mock', VITE_BACKEND_API_URL: '/api/v1' },
    restoreMocks: true, clearMocks: true },
});
