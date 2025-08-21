import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import viteTsconfigPaths from 'vite-tsconfig-paths';

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Load env file based on `mode` in the current working directory.
  const env = loadEnv(mode, process.cwd(), '');
  
  return {
    plugins: [react(), viteTsconfigPaths()],
    server: {
      port: 3000,
      host: true,
      open: true,
    },
    build: {
      outDir: 'build',
      sourcemap: true,
    },
    define: {
      // Make REACT_APP_* variables available for backward compatibility
      'process.env.REACT_APP_API_BASE_URL': JSON.stringify(env.REACT_APP_API_BASE_URL || env.VITE_API_BASE_URL || 'http://localhost:8001'),
      'process.env.REACT_APP_CHAT_TITLE': JSON.stringify(env.REACT_APP_CHAT_TITLE || env.VITE_CHAT_TITLE || 'Talk2Tables Chat'),
      'process.env.REACT_APP_MAX_MESSAGE_LENGTH': JSON.stringify(env.REACT_APP_MAX_MESSAGE_LENGTH || env.VITE_MAX_MESSAGE_LENGTH || '5000'),
      'process.env.REACT_APP_TYPING_DELAY': JSON.stringify(env.REACT_APP_TYPING_DELAY || env.VITE_TYPING_DELAY || '1000'),
      'process.env.REACT_APP_DEBUG': JSON.stringify(env.REACT_APP_DEBUG || env.VITE_DEBUG || 'false'),
    },
  };
});