import { describe, expect, it } from 'vitest';
import {
  COMPANION_SIZE, EDGE, NARROW, bodyHeight, bounds, clampPos, companionFace, fromRatio, homePos, loadRatio,
  panelPlacement, pickAct, pickWalkTarget, saveRatio, stepToward, toRatio, IDLE_ACTS,
} from './companion.js';

const memory = () => { const m = new Map(); return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) }; };

describe('ตำแหน่งและกรอบจอ', () => {
  it('ตำแหน่งตั้งต้นอยู่ล่างขวา ในกรอบ', () => {
    const h = homePos(1200, 800);
    const b = bounds(1200, 800);
    expect(h.y).toBe(b.maxY);
    expect(h.x).toBeLessThanOrEqual(b.maxX);
    expect(h.x).toBeGreaterThan(600);
  });
  it('clampPos ไม่ให้หลุดขอบจอ', () => {
    const b = bounds(1000, 700);
    expect(clampPos({ x: -50, y: -50 }, 1000, 700)).toEqual({ x: b.minX, y: b.minY });
    expect(clampPos({ x: 5000, y: 5000 }, 1000, 700)).toEqual({ x: b.maxX, y: b.maxY });
  });
  it('จอเล็กกว่าตัวก็ไม่พัง', () => {
    const p = clampPos({ x: 100, y: 100 }, 40, 40);
    expect(Number.isFinite(p.x) && Number.isFinite(p.y)).toBe(true);
  });
  it('สัดส่วนไป-กลับให้ตำแหน่งเดิม และปรับตามขนาดจอใหม่', () => {
    const pos = { x: 300, y: 400 };
    const r = toRatio(pos, 1200, 800);
    const back = fromRatio(r, 1200, 800);
    expect(Math.abs(back.x - pos.x)).toBeLessThan(1);
    expect(Math.abs(back.y - pos.y)).toBeLessThan(1);
    const small = fromRatio(r, 600, 500);
    const b = bounds(600, 500);
    expect(small.x).toBeGreaterThanOrEqual(b.minX);
    expect(small.x).toBeLessThanOrEqual(b.maxX);
  });
  it('เก็บ/อ่านตำแหน่งจากที่เก็บ และทนค่าเสีย', () => {
    const s = memory();
    expect(loadRatio(s)).toBeNull();
    saveRatio({ fx: 0.25, fy: 1 }, s);
    expect(loadRatio(s)).toEqual({ fx: 0.25, fy: 1 });
    s.setItem('nongtrip-companion-pos', '{oops');
    expect(loadRatio(s)).toBeNull();
    s.setItem('nongtrip-companion-pos', JSON.stringify({ fx: 9, fy: -3 }));
    expect(loadRatio(s)).toEqual({ fx: 1, fy: 0 });
    expect(() => saveRatio({ fx: 0, fy: 0 }, { setItem() { throw new Error('blocked'); } })).not.toThrow();
    expect(loadRatio({ getItem() { throw new Error('blocked'); } })).toBeNull();
  });
});

describe('การเดิน', () => {
  it('ปลายทางอยู่ในกรอบเสมอ และห่างพอให้เห็นว่าเดิน', () => {
    for (let i = 0; i < 200; i += 1) {
      const x = 8 + Math.random() * 900;
      const t = pickWalkTarget(x, 1000);
      const b = bounds(1000, 0);
      expect(t).toBeGreaterThanOrEqual(b.minX);
      expect(t).toBeLessThanOrEqual(b.maxX);
    }
  });
  it('ชิดขอบซ้ายต้องเดินไปทางขวา', () => {
    const b = bounds(1000, 0);
    expect(pickWalkTarget(b.minX, 1000, COMPANION_SIZE, () => 0.5, () => 0.1)).toBeGreaterThan(b.minX + 100);
  });
  it('ชิดขอบขวาต้องเดินไปทางซ้าย', () => {
    const b = bounds(1000, 0);
    expect(pickWalkTarget(b.maxX, 1000, COMPANION_SIZE, () => 0.5, () => 0.9)).toBeLessThan(b.maxX - 100);
  });
  it('stepToward เดินตามความเร็วและหยุดตรงปลายทาง', () => {
    expect(stepToward(0, 100, 0.5, 64)).toMatchObject({ x: 32, arrived: false, dir: 1 });
    expect(stepToward(100, 0, 0.5, 64)).toMatchObject({ x: 68, arrived: false, dir: -1 });
    expect(stepToward(90, 100, 0.5, 64)).toMatchObject({ x: 100, arrived: true });
  });
});

describe('ท่าทางและอารมณ์', () => {
  it('ค้นอยู่ → คิด, เสร็จ → ยิ้ม, ผิดพลาด → ร้องไห้', () => {
    expect(companionFace({ status: 'searching' })).toEqual({ mood: 'think' });
    expect(companionFace({ status: 'answering' })).toEqual({ mood: 'think' });
    expect(companionFace({ status: 'done' }).expression).toBe('grin');
    expect(companionFace({ status: 'error' }).expression).toBe('crying');
  });
  it('ถูกหิ้วลากตกใจ และชี้แล้วตาเป็นดาว และพิมพ์อยู่ตั้งใจฟัง', () => {
    expect(companionFace({ dragging: true, status: 'done' }).expression).toBe('afraid');
    expect(companionFace({ hover: true }).expression).toBe('star-eyes');
    expect(companionFace({ open: true, typing: true }).expression).toBe('star-eyes');
    expect(companionFace({})).toEqual({ mood: 'front' });
  });
  it('ท่าเล่นเองเลือกจากรายการและไม่หลุดช่วง', () => {
    expect(IDLE_ACTS).toContain(pickAct(() => 0));
    expect(IDLE_ACTS).toContain(pickAct(() => 0.9999));
    expect(IDLE_ACTS).toContain(pickAct(() => 1));
  });
});

describe('หน้าต่างแชต', () => {
  const h = bodyHeight();
  it('มาสคอตอยู่ล่าง → หน้าต่างอยู่เหนือตัว ไม่ทับตัวและไม่หลุดจอ', () => {
    const pos = { x: 1000, y: 800 - h - EDGE };
    const p = panelPlacement(pos, 1200, 800);
    expect(p.sheet).toBe(false);
    expect(p.top + p.height).toBeLessThanOrEqual(pos.y);
    expect(p.left + p.width).toBeLessThanOrEqual(1200 - EDGE);
    expect(p.top).toBeGreaterThanOrEqual(EDGE);
  });
  it('มาสคอตอยู่บน → หน้าต่างอยู่ใต้ตัว', () => {
    const pos = { x: 100, y: 20 };
    const p = panelPlacement(pos, 1200, 800);
    expect(p.top).toBeGreaterThanOrEqual(pos.y + h);
    expect(p.top + p.height).toBeLessThanOrEqual(800 - EDGE);
    expect(p.left).toBeGreaterThanOrEqual(EDGE);
  });
  it('จอแคบเป็นแผ่นเต็มความกว้างติดล่างจอ', () => {
    const p = panelPlacement({ x: 100, y: 300 }, NARROW - 1, 700);
    expect(p).toMatchObject({ sheet: true, left: 8, width: NARROW - 1 - 16 });
    expect(p.top + p.height).toBe(700 - 8);
  });
  it('จอเตี้ยก็ยังได้ความสูงขั้นต่ำและอยู่ในจอ', () => {
    const p = panelPlacement({ x: 600, y: 200 }, 1000, 420);
    expect(p.height).toBeGreaterThanOrEqual(280);
    expect(p.top).toBeGreaterThanOrEqual(EDGE);
  });
});
