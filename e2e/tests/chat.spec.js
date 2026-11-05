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

test('ไปหน้าอื่นแล้วกลับมา หรือรีเฟรช แชตเดิมยังอยู่ และกดแชตใหม่แล้วล้าง', async ({ page }) => {
  await page.goto('/chat');
  await page.locator('#chat-message').fill('คาเฟ่ในเชียงใหม่');
  await page.locator('form button[type=submit]').last().click();
  const log = page.getByRole('log');
  await expect(log).toHaveAttribute('aria-busy', 'false', { timeout: 40_000 });
  await expect(log).toContainText('คาเฟ่ในเชียงใหม่');

  await page.locator('.ntg-side-link').click();                       // ไปหน้าแผนที่ (เปลี่ยนหน้าในแอป)
  await expect(page).toHaveURL(/\/search/);
  await page.goBack();
  await expect(page).toHaveURL(/\/chat/);
  await expect(page.getByRole('log')).toContainText('คาเฟ่ในเชียงใหม่');

  await page.reload();                                                // รีเฟรช: เก็บไว้ในแท็บนี้
  await expect(page.getByRole('log')).toContainText('คาเฟ่ในเชียงใหม่');

  await page.locator('.ntg-new').click();                              // แชตใหม่: ล้างทั้งหน้าจอและที่เก็บ
  await expect(page.locator('.ntg-empty')).toBeVisible();
  await page.reload();
  await expect(page.locator('.ntg-empty')).toBeVisible();
});

test('คำถามต่อเนื่องส่งบทสนทนาก่อนหน้าไปด้วย', async ({ page }) => {
  await page.goto('/chat');
  await page.locator('#chat-message').fill('ที่เที่ยวในเชียงใหม่');
  await page.locator('form button[type=submit]').last().click();
  const log = page.getByRole('log');
  await expect(log).toHaveAttribute('aria-busy', 'false', { timeout: 40_000 });
  const sent = page.waitForRequest((r) => r.url().endsWith('/api/chat') && r.method() === 'POST');
  await page.locator('#chat-message').fill('แล้วคาเฟ่ล่ะ');
  await page.locator('form button[type=submit]').last().click();
  const body = (await sent).postDataJSON();
  expect(body.history?.[0]).toEqual({ role: 'user', content: 'ที่เที่ยวในเชียงใหม่' });
  expect(body.history?.[1]?.role).toBe('assistant');
  await expect(log).toHaveAttribute('aria-busy', 'false', { timeout: 40_000 });
});
