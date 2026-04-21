import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    // happy-dom: jsdom 29 + html-encoding-sniffer 6 даёт ERR_REQUIRE_ESM (@exodus/bytes ESM-only).
    environment: 'happy-dom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: true,
  },
});
