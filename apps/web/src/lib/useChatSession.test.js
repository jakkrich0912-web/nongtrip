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

describe('historyToMessages', () => {
  it('turns a saved chat into user and bot messages, skipping empty ones', async () => {
    const { historyToMessages } = await import('./useChatSession.js');
    const out = historyToMessages({ id: 3, messages: [
      { role: 'user', content: 'คาเฟ่ในน่าน' },
      { role: 'assistant', content: 'พบคาเฟ่ 12 แห่ง' },
      { role: 'assistant', content: '   ' },
    ] });
    expect(out.map((m) => [m.role, m.text])).toEqual([['user', 'คาเฟ่ในน่าน'], ['bot', 'พบคาเฟ่ 12 แห่ง']]);
    expect(out[1]).toMatchObject({ status: 'done', sources: [], restored: true });
    expect(new Set(out.map((m) => m.id)).size).toBe(2);
  });
  it('handles a missing chat', async () => {
    const { historyToMessages } = await import('./useChatSession.js');
    expect(historyToMessages(null)).toEqual([]);
  });
});
