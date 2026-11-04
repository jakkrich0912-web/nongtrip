import { describe, it, expect } from 'vitest';
import { latestOnly } from './latest.js';

// จำลองค้นสองครั้งติดกัน ครั้งแรกตอบช้ากว่า
const later = (ms, v) => new Promise((r) => setTimeout(() => r(v), ms));

describe('latestOnly', () => {
  it('ค้นสองครั้ง คำตอบครั้งแรกมาช้า ต้องเห็นแค่ผลครั้งหลัง', async () => {
    const seq = latestOnly();
    const shown = [];
    const search = (q, ms) => { const t = seq.next(); return later(ms, q).then((r) => { if (seq.isCurrent(t)) shown.push(r); }); };
    await Promise.all([search('ครั้งแรก', 30), search('ครั้งหลัง', 5)]);
    expect(shown).toEqual(['ครั้งหลัง']);
  });
  it('เลือกที่พักแล้ว (cancel) คำตอบที่ค้างอยู่ต้องไม่กลับมาโชว์หมุด', async () => {
    const seq = latestOnly();
    const shown = [];
    const t = seq.next();
    const p = later(10, ['หมุดเก่า']).then((r) => { if (seq.isCurrent(t)) shown.push(r); });
    seq.cancel();
    await p;
    expect(shown).toEqual([]);
  });
});
