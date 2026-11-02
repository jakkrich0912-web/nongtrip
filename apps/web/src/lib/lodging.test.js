import { describe, it, expect } from 'vitest';
import { lodgingAround, attachPreviews } from './lodging.js';

const o = { lat: 18.79, lon: 98.98 };
const near = { id: 'n', name: 'ใกล้', lat: 18.80, lon: 98.98 };   // ~1 กม.
const mid = { id: 'm', name: 'กลาง', lat: 18.85, lon: 98.98 };    // ~6.7 กม.
const far = { id: 'f', name: 'ไกล', lat: 19.0, lon: 98.98 };      // ~23 กม.

describe('lodgingAround', () => {
  it('ใช้ 5 กม. เมื่อมีที่พักในรัศมี', () => {
    const r = lodgingAround(o, [mid, near, far]);
    expect(r.meta.radius_km).toBe(5);
    expect(r.items.map((l) => l.id)).toEqual(['n']);
    expect(r.meta.notes).toEqual([]);
  });
  it('ขยายเป็น 10 กม. และบอกผู้ใช้เมื่อ 5 กม. ไม่พบ', () => {
    const r = lodgingAround(o, [mid, far]);
    expect(r.meta.radius_km).toBe(10);
    expect(r.items.map((l) => l.id)).toEqual(['m']);
    expect(r.meta.notes[0]).toContain('10 กม.');
  });
  it('ไม่ขยายเกิน 10 กม.', () => {
    expect(lodgingAround(o, [far]).items).toEqual([]);
  });
});

describe('attachPreviews', () => {
  it('แนบสถานที่ใกล้สุด 3 แห่งเรียงใกล้ไปไกล และนับทั้งหมดใน 30 กม.', () => {
    const places = [0.01, 0.02, 0.03, 0.04, 1].map((d, i) => ({ id: `p${i}`, lat: 18.80 + d, lon: 98.98 }));
    const [l] = attachPreviews([near], places);
    expect(l.places_preview.map((p) => p.id)).toEqual(['p0', 'p1', 'p2']);
    expect(l.places_total).toBe(4);
  });
});
