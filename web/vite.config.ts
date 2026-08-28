import preact from '@preact/preset-vite';
import { defineConfig } from 'vite';

declare const process: {
  env: {
    BUNNYLAND_STUDIO_BASE?: string;
    BUNNYLAND_API_PROXY?: string;
  };
};

export default defineConfig({
  base: process.env.BUNNYLAND_STUDIO_BASE || '/studio/',
  plugins: [preact()],
  server: {
    proxy: {
      '/api': {
        changeOrigin: true,
        ws: true,
        rewrite: path => path.replace(/^\/api/, '') || '/',
        target: process.env.BUNNYLAND_API_PROXY || 'http://127.0.0.1:8765',
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
