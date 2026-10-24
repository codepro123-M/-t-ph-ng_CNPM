import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const upstream = env.SMARTSTAY_API_TARGET || 'http://127.0.0.1:8001';
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0', port: 4173, strictPort: true,
      allowedHosts: ['terminal.local'],
      proxy: { '/api': {
        target: upstream, changeOrigin: true,
        rewrite: path => path.replace(/^\/api(?=\/|$)/, ''),
      } },
    },
    preview: { host: '0.0.0.0', port: 4173 },
    build: { sourcemap: false, target: 'es2022' },
  };
});
