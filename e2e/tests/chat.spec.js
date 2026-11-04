import { expect, test } from '@playwright/test';

test('ถามแชตเรื่องที่เที่ยวแล้วได้คำตอบพร้อมรายชื่อสถานที่', async ({ page }) => {
  await page.goto('/chat');
  const box = page.locator('#chat-message');
  await box.fill('ที่เที่ยวในเชียงใหม่');
  await page.locator('form button[type=submit]').last().click();
  const log = page.getByRole('log');
  await expect(log).toContainText('ที่เที่ยวในเชียงใหม่');                          // ข้อความของเรา
  await expect(log).toHaveAttribute('aria-busy', 'false', { timeout: 40_000 });     // ตอบเสร็จแล้ว
  await expect(log).toContainText(/กม\.|เชียงใหม่/);
  const text = await log.innerText();
  expect(text).not.toMatch(/ราคา\s*\d|บาท/);                                      // ไม่มีราคาที่ยืนยันไม่ได้
});

test('ถามราคาแล้วระบบไม่แต่งตัวเลข', async ({ page }) => {
  await page.goto('/chat');
  await page.locator('#chat-message').fill('ค่าเข้าดอยสุเทพกี่บาท');
  await page.locator('form button[type=submit]').last().click();
  const log = page.getByRole('log');
  await expect(log).toHaveAttribute('aria-busy', 'false', { timeout: 40_000 });
  expect(await log.innerText()).not.toMatch(/\d+\s*บาท/);
});
