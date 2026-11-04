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

describe('จำบทสนทนา', () => {
  it('historyFor: ส่งเฉพาะคำถามและคำตอบที่จบแล้ว ไม่เกิน 6 ข้อความท้าย ตัดข้อความยาว', async () => {
    const { historyFor, HISTORY_TURNS } = await import('./useChatSession.js');
    const msgs = [
      { id: 'user-1', role: 'user', text: 'ที่เที่ยวในน่าน' },
      { id: 1, role: 'bot', text: 'มีวัดภูมินทร์', status: 'done' },
      { id: 'user-2', role: 'user', text: 'แล้วคาเฟ่ล่ะ' },
      { id: 2, role: 'bot', text: 'ครึ่งทาง', status: 'stopped' },
      { id: 'user-3', role: 'user', text: '  ' },
      { id: 3, role: 'bot', text: 'ก'.repeat(900), status: 'done' },
    ];
    expect(historyFor(msgs)).toEqual([
      { role: 'user', content: 'ที่เที่ยวในน่าน' },
      { role: 'assistant', content: 'มีวัดภูมินทร์' },
      { role: 'user', content: 'แล้วคาเฟ่ล่ะ' },
      { role: 'assistant', content: 'ก'.repeat(400) },
    ]);
    const many = Array.from({ length: 20 }, (_, i) => ({ id: `user-${i}`, role: 'user', text: `q${i}` }));
    expect(historyFor(many)).toHaveLength(HISTORY_TURNS);
    expect(historyFor(many).at(-1).content).toBe('q19');
    expect(historyFor([])).toEqual([]);
  });

  it('packChat/unpackChat: กู้ได้เฉพาะผู้ใช้คนเดิม คำตอบที่ค้างถือว่าหยุดแล้ว', async () => {
    const { packChat, unpackChat, KEEP_MESSAGES } = await import('./useChatSession.js');
    const messages = [
      { id: 'user-1', role: 'user', text: 'คาเฟ่ในเชียงใหม่' },
      { id: 1, role: 'bot', text: 'มีร้าน', status: 'done' },
      { id: 'user-2', role: 'user', text: 'แล้ววัดล่ะ' },
      { id: 2, role: 'bot', text: 'กำลัง', status: 'answering' },
      { id: 'user-3', role: 'user', text: 'อีกข้อ' },
      { id: 3, role: 'bot', text: '', status: 'searching' },
    ];
    const raw = JSON.stringify(packChat({ uid: 7, messages, context: { lat: 18.7, lon: 98.9, name: 'ที่พัก' }, chatId: 12, lastProvince: 'เชียงใหม่' }));
    const kept = unpackChat(raw, 7);
    expect(kept.chatId).toBe(12);
    expect(kept.lastProvince).toBe('เชียงใหม่');
    expect(kept.context).toEqual({ lat: 18.7, lon: 98.9, name: 'ที่พัก' });
    expect(kept.messages.map((m) => m.status ?? 'user')).toEqual(['user', 'done', 'user', 'stopped', 'user']);
    expect(unpackChat(raw, null)).toBeNull();          // ออกจากระบบแล้วไม่เห็นแชตของบัญชี
    expect(unpackChat(raw, 8)).toBeNull();             // คนอื่นไม่เห็น
    expect(unpackChat('{bad', 7)).toBeNull();
    expect(unpackChat(null, null)).toBeNull();
    const guest = unpackChat(JSON.stringify(packChat({ messages })), null);
    expect(guest.chatId).toBeNull();
    const long = packChat({ messages: Array.from({ length: 100 }, (_, i) => ({ id: `user-${i}`, role: 'user', text: `${i}` })) });
    expect(long.messages).toHaveLength(KEEP_MESSAGES);
    expect(unpackChat(JSON.stringify({ ...long, context: { lat: 'x' } }), null).context).toBeNull();
  });
});
