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

import { RADIUS_OPTIONS, radiusComplete, withinRadius } from './geo.js';

describe('radius filter', () => {
  const items = [{ id: 'a', distance_km: 3 }, { id: 'b', distance_km: 9.9 }, { id: 'c', distance_km: 10 }, { id: 'd', distance_km: 21 }];
  it('กรองตามรัศมีแบบรวมขอบ และคงลำดับเดิม', () => {
    expect(withinRadius(items, 10).map((p) => p.id)).toEqual(['a', 'b', 'c']);
    expect(withinRadius(items, 5).map((p) => p.id)).toEqual(['a']);
  });
  it('ตัวเลือกไม่เกิน 30 กม.', () => {
    expect(Math.max(...RADIUS_OPTIONS)).toBe(30);
    expect(RADIUS_OPTIONS.every((r) => r <= 30)).toBe(true);
  });
  it('รู้ว่าโหลดครบในรัศมีหรือยัง', () => {
    expect(radiusComplete(items, 4, 30)).toBe(true);        // โหลดครบทั้งหมด
    expect(radiusComplete(items, 50, 15)).toBe(true);       // แห่งสุดท้าย (21) เลย 15 ไปแล้ว
    expect(radiusComplete(items, 50, 30)).toBe(false);      // ยังมีอีก และอาจยังอยู่ในรัศมี
  });
});
