import { describe, expect, it } from 'vitest';
import { QUICK_PROVINCES, chatSuggestions, userChanged } from './useChatSession.js';

describe('ล้างแชตเมื่อผู้ใช้เปลี่ยน', () => {
  it('ล็อกเอาต์หรือเปลี่ยนคน ต้องล้าง', () => {
    expect(userChanged(5, null)).toBe(true);
    expect(userChanged(5, 7)).toBe(true);
  });
  it('ไม่ล็อกอินแล้วล็อกอิน (คนเดิมคุยต่อ) และคนเดิมรีเฟรช ไม่ล้าง', () => {
    expect(userChanged(null, 5)).toBe(false);
    expect(userChanged(5, 5)).toBe(false);
    expect(userChanged(null, null)).toBe(false);
    expect(userChanged(undefined, 3)).toBe(false);
  });
});

describe('ปุ่มและคำถามแนะนำ', () => {
  it('จังหวัดด่วนมีทั้งชื่อไทยและอังกฤษ', () => {
    for (const [th, en] of QUICK_PROVINCES) { expect(th).toBeTruthy(); expect(en).toMatch(/^[A-Z]/); }
  });
  it('คำถามแนะนำเปลี่ยนตามว่ามีจุดค้นหรือยัง', () => {
    expect(chatSuggestions(true)[0][0]).toContain('ใกล้ที่พัก');
    expect(chatSuggestions(false)[0][0]).toContain('เชียงใหม่');
  });
});
