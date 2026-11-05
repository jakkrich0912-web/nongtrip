import { expect, test } from '@playwright/test';
import { PASSWORD, openAccountMenu, signUp } from './helpers.js';

const ADMIN = process.env.E2E_ADMIN_EMAIL;

test('ผู้ใช้ทั่วไปเปิดแดชบอร์ดแล้วเห็นหน้าห้ามเข้า และ API ตอบ 403', async ({ page }) => {
  await signUp(page);
  await page.goto('/admin');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('หน้านี้สำหรับผู้ดูแลระบบ');
  expect((await page.request.get('/api/admin/overview')).status()).toBe(403);
});

test('ผู้ดูแลเข้าแดชบอร์ดจากเมนูบัญชี เห็นยอดรวมและการค้นที่เพิ่งเกิด', async ({ page }) => {
  test.skip(!ADMIN, 'ตั้ง E2E_ADMIN_EMAIL ให้ตรงกับ ADMIN_EMAILS ของระบบก่อน');
  // บัญชีผู้ดูแลอาจมีอยู่แล้วจากการรันครั้งก่อน ลองเข้าสู่ระบบก่อน (คุกกี้ใช้ร่วมกับหน้าเว็บ) ไม่ได้ค่อยสมัคร
  const r = await page.request.post('/api/auth/login', { data: { email: ADMIN, password: PASSWORD } });
  if (r.status() !== 200) await signUp(page, ADMIN);
  const before = (await (await page.request.get('/api/admin/overview')).json()).usage.search_total;
  await page.request.get('/api/places/nearby?lat=18.7883&lon=98.9853');               // การค้นหนึ่งครั้ง

  await page.goto('/');
  await (await openAccountMenu(page)).getByRole('menuitem', { name: /แดชบอร์ดผู้ดูแล/ }).click();
  await expect(page).toHaveURL(/\/admin$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('ภาพรวมของน้องทริป');
  await expect(page.locator('.adm-tile')).toHaveCount(4);
  await expect(page.locator('.adm-tile', { hasText: 'การค้น' }).locator('b')).toHaveText(String(before + 1));
  await expect(page.locator('.adm-col')).toHaveCount(28);                             // สองกราฟ กราฟละ 14 วัน
  await expect(page.locator('.adm-meter')).toHaveCount(2);
  await page.locator('.adm-col').nth(13).hover();
  await expect(page.locator('.adm-tip')).toBeVisible();
});

test('แจ้งข้อมูลผิดจากหน้าสถานที่ แล้วผู้ดูแลเห็นและลบได้', async ({ page, browser }) => {
  test.skip(!ADMIN, 'ตั้ง E2E_ADMIN_EMAIL ให้ตรงกับ ADMIN_EMAILS ของระบบก่อน');
  const note = `ทดสอบ ${Date.now()}`;
  await page.goto('/places/v%3Ap01');
  await page.getByRole('button', { name: 'แจ้งข้อมูลผิด' }).click();
  await page.getByRole('radio', { name: 'ตำแหน่งบนแผนที่ผิด' }).check();
  await page.locator('.report-note textarea').fill(note);
  await page.getByRole('button', { name: 'ส่งให้ผู้ดูแล' }).click();
  await expect(page.getByText('ส่งให้ผู้ดูแลตรวจแล้ว')).toBeVisible();

  const admin = await (await browser.newContext()).newPage();
  const r = await admin.request.post('/api/auth/login', { data: { email: ADMIN, password: PASSWORD } });
  if (r.status() !== 200) await signUp(admin, ADMIN);
  await admin.goto('/admin');
  const item = admin.locator('.adm-reports li', { hasText: note });
  await expect(item).toContainText('ตำแหน่งบนแผนที่ผิด');
  await item.getByRole('button', { name: 'ตรวจแล้ว ลบ' }).click();
  await expect(admin.locator('.adm-reports li', { hasText: note })).toHaveCount(0);
});
