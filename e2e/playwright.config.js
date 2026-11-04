// เทสต์ใช้งานจริงผ่านเบราว์เซอร์ รันกับระบบที่เปิดอยู่แล้ว (docker compose up) ไม่ได้เปิดระบบเอง
//   E2E_BASE_URL       ที่อยู่ของเว็บ ค่าเริ่มต้น http://localhost:8080
//   E2E_ADMIN_EMAIL    อีเมลที่อยู่ใน ADMIN_EMAILS ของระบบนั้น ไม่ตั้ง = ข้ามเทสต์แดชบอร์ด
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    locale: 'th-TH',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] }, testIgnore: /\.mobile\.spec\.js$/ },
    { name: 'mobile', use: { ...devices['Pixel 7'] }, testMatch: /\.mobile\.spec\.js$/ },
  ],
});
