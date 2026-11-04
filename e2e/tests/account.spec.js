import { expect, test } from '@playwright/test';
import { PASSWORD, logIn, openAccountMenu, signUp, uniqueEmail } from './helpers.js';

const NEW_PASSWORD = 'e2e-new-password-456';

test('สมัครแล้วหัวเว็บเป็นรูปโปรไฟล์ เมนูบัญชีพาไปทริปของฉันและปิดด้วย Esc ได้', async ({ page }) => {
  const email = await signUp(page);
  await expect(page.locator('.nt-login-link')).toHaveCount(0);
  await expect(page.locator('.nt-avatar').first()).toHaveText(email[0].toUpperCase());
  let menu = await openAccountMenu(page);
  await expect(menu).toContainText(email);
  await expect(menu.getByRole('menuitem', { name: /แดชบอร์ดผู้ดูแล/ })).toHaveCount(0);   // ไม่ใช่ผู้ดูแล
  await page.keyboard.press('Escape');
  await expect(page.getByRole('menu')).toHaveCount(0);
  await expect(page.locator('.nt-account-btn')).toBeFocused();
  menu = await openAccountMenu(page);
  await menu.getByRole('menuitem', { name: /ทริปของฉัน/ }).click();
  await expect(page).toHaveURL(/\/me$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('ทริปของฉัน');
});

test('เปลี่ยนรหัสผ่าน: รหัสเดิมผิดถูกปฏิเสธ รหัสถูกเปลี่ยนได้ และเข้าด้วยรหัสใหม่ได้', async ({ page }) => {
  const email = await signUp(page);
  const menu = await openAccountMenu(page);
  await menu.getByRole('menuitem', { name: /ตั้งค่าบัญชี/ }).click();
  await expect(page).toHaveURL(/\/settings$/);
  const fields = page.locator('.st-form input');
  await fields.nth(0).fill('wrong-password-000');
  await fields.nth(1).fill(NEW_PASSWORD);
  await fields.nth(2).fill(NEW_PASSWORD);
  await page.getByRole('button', { name: 'เปลี่ยนรหัสผ่าน' }).click();
  await expect(page.locator('.st-form .auth-error')).toHaveText('รหัสผ่านปัจจุบันไม่ถูกต้อง');
  await fields.nth(0).fill(PASSWORD);
  await page.getByRole('button', { name: 'เปลี่ยนรหัสผ่าน' }).click();
  await expect(page.locator('.st-ok')).toContainText('เปลี่ยนรหัสผ่านแล้ว');

  await (await openAccountMenu(page)).getByRole('menuitem', { name: 'ออกจากระบบ' }).click();
  await expect(page.locator('.nt-login-link')).toBeVisible();
  await logIn(page, email, PASSWORD);
  await expect(page.locator('.nt-auth-error, [role=alert]').first()).toBeVisible();     // รหัสเดิมใช้ไม่ได้แล้ว
  await logIn(page, email, NEW_PASSWORD);
  await expect(page.locator('.nt-account-btn')).toBeVisible();
});

test('ออกจากระบบแล้วคุกกี้เดิมใช้ต่อไม่ได้ (ยกเลิกเซสชันฝั่งเซิร์ฟเวอร์)', async ({ page, context }) => {
  await signUp(page);
  const copied = (await context.cookies()).find((c) => c.name === 'nt_session');
  expect(copied).toBeTruthy();
  await (await openAccountMenu(page)).getByRole('menuitem', { name: 'ออกจากระบบ' }).click();
  await expect(page.locator('.nt-login-link')).toBeVisible();
  await context.addCookies([copied]);                                                 // คนที่คัดลอกคุกกี้ไว้
  const r = await page.request.get('/api/auth/me');
  expect(r.status()).toBe(401);
});

test('ผู้ที่ไม่ได้เข้าสู่ระบบเปิดหน้าตั้งค่าแล้วถูกพาไปหน้าเข้าสู่ระบบ', async ({ page }) => {
  await page.goto('/settings');
  await expect(page).toHaveURL(/\/login$/);
});

test('บันทึกสถานที่โปรดจากหน้าจังหวัด แล้วเห็นในทริปของฉัน', async ({ page }) => {
  await signUp(page, uniqueEmail('fav'));
  await page.goto('/provinces/%E0%B9%80%E0%B8%8A%E0%B8%B5%E0%B8%A2%E0%B8%87%E0%B9%83%E0%B8%AB%E0%B8%A1%E0%B9%88');
  const card = page.locator('.prov-grid-cards > li').first();
  const name = (await card.locator('strong').first().innerText()).trim();
  await card.locator('button').first().click();
  await page.goto('/me');
  await expect(page.getByText(name).first()).toBeVisible();
});
