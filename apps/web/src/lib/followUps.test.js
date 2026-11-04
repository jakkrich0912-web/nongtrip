import { describe, expect, it } from 'vitest';
import { MAX_FOLLOW_UPS, followUps } from './followUps.js';

const bot = (extra) => ({ role: 'bot', status: 'done', text: 'ตอบแล้ว', ...extra });
const place = (kind) => ({ id: Math.random(), kind });

describe('ปุ่มถามต่อ', () => {
  it('คำตอบที่มีสถานที่และคลังความรู้ เริ่มด้วยเล่าเพิ่ม และไม่เกิน 4 ปุ่ม', () => {
    const out = followUps(bot({ places: { items: [place('attraction'), place('attraction')], total: 30 }, sources: [{ id: 'k:p01:0' }] }));
    expect(out[0][0]).toBe('เล่าเพิ่ม');
    expect(out.map((x) => x[0])).toContain('คาเฟ่แถวนี้');
    expect(out.map((x) => x[0])).toContain('ขอดูที่เที่ยว 10 แห่ง');
    expect(out.length).toBeLessThanOrEqual(MAX_FOLLOW_UPS);
  });

  it('ผลเป็นคาเฟ่ล้วน เสนอที่เที่ยว ผลปนกันไม่เสนอสลับประเภท และไม่มีดูเพิ่มเมื่อแสดงครบแล้ว', () => {
    expect(followUps(bot({ places: { items: [place('cafe')] } })).map((x) => x[0])).toEqual(['ที่เที่ยวแถวนี้', 'ที่พักใกล้ ๆ']);
    expect(followUps(bot({ places: { items: [place('cafe'), place('attraction')], total: 2 } })).map((x) => x[0])).toEqual(['ที่พักใกล้ ๆ']);
  });

  it('ถามช่วงเวลาได้เฉพาะคำตอบที่อ้างคลังความรู้', () => {
    const k = followUps(bot({ places: { items: [place('cafe')], total: 9 }, sources: [{ id: 'k' }] })).map((x) => x[0]);
    expect(k).toEqual(['เล่าเพิ่ม', 'ที่เที่ยวแถวนี้', 'ขอดูคาเฟ่ 10 แห่ง', 'ที่พักใกล้ ๆ']);
  });

  it('ไม่มีปุ่มเมื่อคำตอบยังไม่จบ ถามกลับว่าแถวไหน ให้เลือกที่พัก ไม่มีสถานที่ หรือเป็นข้อความผู้ใช้', () => {
    const places = { items: [place('cafe')] };
    expect(followUps(bot({ places, status: 'answering' }))).toEqual([]);
    expect(followUps(bot({ places, ask: 'location' }))).toEqual([]);
    expect(followUps(bot({ places, lodgings: { items: [{ id: 1 }] } }))).toEqual([]);
    expect(followUps(bot({}))).toEqual([]);
    expect(followUps({ role: 'user', text: 'x' })).toEqual([]);
    expect(followUps(null)).toEqual([]);
  });
});
