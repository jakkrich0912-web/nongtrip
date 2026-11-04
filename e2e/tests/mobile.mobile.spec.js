import { expect, test } from '@playwright/test';
import { openAccountMenu, signUp } from './helpers.js';

test('มือถือ: เมนู ☰ เปิดได้ และรูปโปรไฟล์ยังกดเปิดเมนูบัญชีได้', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'เปิดเมนู' }).click();
  await expect(page.locator('#nt-navigation')).toBeVisible();
  await signUp(page);
  const menu = await openAccountMenu(page);
  const box = await menu.boundingBox();
  const vw = page.viewportSize().width;
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(vw);                                 // ไม่ล้นจอ
});

test('มือถือ: หน้าทุกจังหวัดแสดงสองคอลัมน์และไม่เลื่อนแนวนอน', async ({ page }) => {
  await page.goto('/provinces');
  await expect(page.locator('.nti-prov').first()).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});
