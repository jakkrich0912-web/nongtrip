import { expect, test } from '@playwright/test';

test('หน้าแรกเปิดได้ และเมนูหลักพาไปหน้าค้นหา', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('จองที่พักแล้ว');
  await page.getByRole('navigation', { name: 'เมนูหลัก' }).getByRole('link', { name: 'ค้นหารอบที่พัก' }).click();
  await expect(page).toHaveURL(/\/search/);
});

test('หน้าทุกจังหวัดมีครบ 77 ค้นชื่ออังกฤษได้ และกดเข้าหน้าจังหวัดได้', async ({ page }) => {
  await page.goto('/provinces');
  await expect(page.getByText('แสดง 77 จังหวัด')).toBeVisible();
  await expect(page.locator('.nti-region')).toHaveCount(6);
  await page.getByRole('searchbox').fill('chiang mai');
  await expect(page.locator('.nti-prov')).toHaveCount(1);
  await page.locator('.nti-prov').click();
  await expect(page).toHaveURL(/\/provinces\/%E0%B9%80%E0%B8%8A%E0%B8%B5%E0%B8%A2%E0%B8%87%E0%B9%83%E0%B8%AB%E0%B8%A1%E0%B9%88$/);
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('เชียงใหม่');
  await expect(page.getByText(/สถานที่ที่ตรวจที่มาแล้ว \d+ แห่ง/)).toBeVisible();
});

test('สลับเป็นภาษาอังกฤษแล้วชื่อจังหวัดเป็นภาษาอังกฤษ', async ({ page }) => {
  await page.goto('/provinces');
  await page.getByRole('group', { name: 'ภาษา' }).getByRole('button', { name: 'EN' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('Pick a province');
  await expect(page.locator('.nti-prov strong', { hasText: 'Chiang Mai' })).toBeVisible();
});

test('หน้าเกี่ยวกับเราแสดงตัวเลขจริงจากระบบและเครดิตข้อมูล', async ({ page }) => {
  await page.goto('/about');
  await expect(page.getByRole('heading', { level: 1 })).toContainText('เริ่มจากที่พัก');
  const stats = page.locator('.nta-stats dd');
  await expect(stats).toHaveCount(3);
  await expect(stats.nth(1)).toHaveText(/^\d[\d,]*$/);           // โหลดจาก /api/health แล้ว ไม่ใช่ขีด
  await expect(page.getByText('© OpenStreetMap contributors').first()).toBeVisible();
  await expect(page.getByText('CC BY-SA 4.0').first()).toBeVisible();
});

test('หน้าความเป็นส่วนตัวมีทุกหัวข้อในสารบัญ', async ({ page }) => {
  await page.goto('/privacy');
  for (const id of ['summary', 'stored', 'outside', 'device', 'logs', 'control', 'security', 'contact']) {
    await expect(page.locator(`section#${id} h2`)).toBeVisible();
  }
  await expect(page.locator('.nti-callout')).toHaveCount(1);         // บอกสถานะแชตตามระบบจริง
});

test('ลิงก์ผิดแสดงหน้าไม่พบหน้า ไม่เด้งกลับหน้าแรก', async ({ page }) => {
  await page.goto('/no-such-page');
  await expect(page.getByRole('heading', { level: 1 })).toHaveText('ไม่พบหน้านี้');
  await expect(page.locator('code')).toHaveText('/no-such-page');
  await page.getByRole('link', { name: 'ดูทุกจังหวัด' }).click();
  await expect(page).toHaveURL(/\/provinces$/);
});
