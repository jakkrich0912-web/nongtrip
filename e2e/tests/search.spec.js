import { expect, test } from '@playwright/test';

// ใจกลางเมืองเชียงใหม่ จังหวัดนี้มีทั้งข้อมูลที่ตรวจแล้วและข้อมูล OSM ที่เก็บไว้
const CM = { lat: 18.7883, lon: 98.9853, name: 'ที่พักทดสอบ' };

test('ค้นรอบที่พักได้รายการเรียงใกล้ไปไกล บอกว่าเป็นระยะเส้นตรง และมีปุ่มนำทาง', async ({ page }) => {
  await page.goto(`/search?lat=${CM.lat}&lon=${CM.lon}&name=${encodeURIComponent(CM.name)}`);
  const items = page.locator('ol.track > li');
  await expect(items.first()).toBeVisible();
  expect(await items.count()).toBeGreaterThan(3);
  const km = (await page.locator('ol.track .km').allInnerTexts()).map((x) => parseFloat(x));
  expect(km.every((v) => Number.isFinite(v) && v <= 30)).toBe(true);
  expect([...km].sort((a, b) => a - b)).toEqual(km);
  await expect(page.locator('ol.track .km').first()).toContainText('เส้นตรง');
  await expect(items.first().getByRole('link', { name: 'นำทาง' })).toHaveAttribute('href', /google\.com\/maps/);
  await expect(page.getByText(/OpenStreetMap/).first()).toBeVisible();
});

test('ตัวกรองรัศมีลดรายการและไม่มีระยะเกินรัศมี', async ({ page }) => {
  await page.goto(`/search?lat=${CM.lat}&lon=${CM.lon}&name=${encodeURIComponent(CM.name)}`);
  await expect(page.locator('ol.track > li').first()).toBeVisible();
  const before = await page.locator('ol.track > li').count();
  const chips = page.getByRole('group', { name: 'รัศมีจากที่พัก (ระยะเส้นตรง)' });
  await chips.getByRole('button', { name: 'ไม่เกิน 5 กม.' }).click();
  await expect(chips.getByRole('button', { name: 'ไม่เกิน 5 กม.' })).toHaveAttribute('aria-pressed', 'true');
  await expect.poll(async () => page.locator('ol.track > li').count()).toBeLessThanOrEqual(before);
  const km = (await page.locator('ol.track .km').allInnerTexts()).map((x) => parseFloat(x));
  expect(km.every((v) => v <= 5)).toBe(true);
});
