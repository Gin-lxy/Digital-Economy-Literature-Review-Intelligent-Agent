import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: false,
    // 禁用对 stdin 的侦听（移除"等待"提示）
    middlewareMode: false,
  },
});
