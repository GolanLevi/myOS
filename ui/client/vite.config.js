import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');

  // When running inside Docker, the Express server is at myos_ui_server:5000
  // When running locally, it's at localhost:5000
  const apiProxyTarget  = env.VITE_API_TARGET      || 'http://localhost:5000';

  // When running inside Docker, the Python FastAPI is at server:8000
  // When running locally, it's at localhost:8080
  const realProxyTarget = env.VITE_REAL_API_PROXY_TARGET || 'http://localhost:8080';

  return {
    plugins: [react()],
    server: {
      port: 5173,
      host: '0.0.0.0',  // Required inside Docker for external access
      proxy: {
        '/api': {
          target: apiProxyTarget,
          changeOrigin: true,
        },
        '/real-api': {
          target: realProxyTarget,
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/real-api/, ''),
        },
      },
    },
  };
});
