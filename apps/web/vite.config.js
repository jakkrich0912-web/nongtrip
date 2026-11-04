import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'node:url';

// อ่านข้อมูลสถานที่ที่ตรวจที่มาแล้วจาก services/places/data โดยตรง (ไม่คัดลอกซ้ำ)
const dataDir = fileURLToPath(new URL('../../services/places/data', import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@data': dataDir } },
  server: {
    port: 5173,
    fs: { allow: ['../..'] },
    proxy: { '/api': process.env.VITE_API_URL ?? 'http://localhost:8000' },
  },
});
