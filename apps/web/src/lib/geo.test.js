import { describe, it, expect } from 'vitest';
import { placesAround, validateResults, haversineKm } from './geo.js';

const o = { lat: 18.79, lon: 98.98 };
const places = [
  { id: 'a', lat: 18.80, lon: 98.92 },
  { id: 'b', lat: 18.79, lon: 98.99 },
  { id: 'c', lat: 13.75, lon: 100.5 },
];

describe('placesAround', () => {
  it('เรียงใกล้ไปไกล และตัดที่เกิน 30 กม.', () => {
    const r = placesAround(o, places);
    expect(r.map((p) => p.id)).toEqual(['b', 'a']);
    expect(validateResults(r).ok).toBe(true);
  });
  it('ไม่ยอมให้รัศมีเกิน 30 กม.', () => {
    expect(placesAround(o, places, 9999).some((p) => p.id === 'c')).toBe(false);
  });
  it('ระยะกรุงเทพ-เชียงใหม่ประมาณ 580 กม.', () => {
    expect(Math.round(haversineKm(o, places[2]) / 10)).toBe(58);
  });
});
