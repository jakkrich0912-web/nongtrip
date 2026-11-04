import { describe, expect, it } from 'vitest';
import { groupChats } from './chatHistory.js';

describe('groupChats', () => {
  const now = new Date(2026, 10, 4, 10, 0, 0); // 4 พ.ย. 10:00 เวลาเครื่อง
  const at = (d, h) => new Date(2026, 10, d, h).toISOString();
  it('puts chats into today / yesterday / previous 7 days / older, keeping order', () => {
    const items = [
      { id: 1, updated_at: at(4, 9) }, { id: 2, updated_at: at(4, 0) },
      { id: 3, updated_at: at(3, 23) }, { id: 4, updated_at: at(30 - 30 + 1, 12) },
      { id: 5, updated_at: '2026-09-01T00:00:00Z' }, { id: 6, updated_at: 'nonsense' },
    ];
    const g = groupChats(items, now);
    expect(g.map((x) => [x.key, x.items.map((c) => c.id)])).toEqual([
      ['today', [1, 2]], ['yesterday', [3]], ['week', [4]], ['older', [5, 6]],
    ]);
  });
  it('skips empty groups', () => {
    expect(groupChats([], now)).toEqual([]);
    expect(groupChats(undefined, now)).toEqual([]);
  });
});
