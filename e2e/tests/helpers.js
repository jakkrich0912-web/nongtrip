import { expect } from '@playwright/test';

export const PASSWORD = 'e2e-password-123';
// อีเมลไม่ซ้ำกันทุกครั้งที่รัน ฐานข้อมูลเดิมก็รันซ้ำได้
export const uniqueEmail = (tag = 'user') => `e2e-${tag}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`;

// สมัครผ่านหน้าเว็บจริง แล้วรอจนหัวเว็บเปลี่ยนเป็นรูปโปรไฟล์
export async function signUp(page, email = uniqueEmail(), password = PASSWORD) {
  await page.goto('/signup');
  await page.locator('input[type=email]').fill(email);
  await page.locator('input[type=password]').first().fill(password);
  await page.locator('form button[type=submit]').click();
  await expect(page.locator('.nt-account-btn')).toBeVisible();
  return email;
}

export async function logIn(page, email, password = PASSWORD) {
  await page.goto('/login');
  await page.locator('input[type=email]').fill(email);
  await page.locator('input[type=password]').first().fill(password);
  await page.locator('form button[type=submit]').click();
}

export async function openAccountMenu(page) {
  await page.locator('.nt-account-btn').click();
  const menu = page.getByRole('menu');
  await expect(menu).toBeVisible();
  return menu;
}
