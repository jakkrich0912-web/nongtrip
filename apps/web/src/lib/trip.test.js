import { describe, expect, it } from 'vitest';
import { compareCounts, groupNearby, nextStop, orderStops } from './trip.js';

const stay = { lat: 18.79, lon: 98.98 };
const at = (id, km, extra = {}) => ({ id, name_th: id, lat: 18.79 + km / 111.19, lon: 98.98, kind: 'attraction', source: 'osm', ...extra });

describe('ทริปจากสถานที่โปรด', () => {
  it('เรียงใกล้ไปไกลจากที่พัก และไม่มีที่พักคงลำดับเดิม', () => {
    const favs = [at('ไกล', 9), at('ใกล้', 1), at('กลาง', 4)];
    expect(orderStops(favs, stay).map((p) => p.id)).toEqual(['ใกล้', 'กลาง', 'ไกล']);
    expect(orderStops(favs, stay)[0].distance_km).toBeCloseTo(1, 1);
    expect(orderStops(favs, null).map((p) => p.distance_km)).toEqual([null, null, null]);
    expect(orderStops([{ id: 'x', lat: null, lon: 1 }], stay)).toEqual([]);
  });

  it('จุดถัดไปข้ามจุดที่ติ๊กแล้ว ครบแล้วคืน null', () => {
    const stops = orderStops([at('a', 1), at('b', 2)], stay);
    expect(nextStop(stops, new Set()).id).toBe('a');
    expect(nextStop(stops, new Set(['a'])).id).toBe('b');
    expect(nextStop(stops, new Set(['a', 'b']))).toBe(null);
  });

  it('จับกลุ่มจุดที่ห่างกันไม่เกิน 2 กม. ต่อกันเป็นสาย ชื่อกลุ่มใช้สถานที่ที่ตรวจแล้ว', () => {
    const groups = groupNearby([at('a', 0), at('b', 1.5, { source: 'verified' }), at('c', 3), at('d', 10)]);
    expect(groups).toHaveLength(1);
    expect(groups[0].items.map((p) => p.id).sort()).toEqual(['a', 'b', 'c']);
    expect(groups[0].anchor.id).toBe('b');
    expect(groups[0].span_km).toBeCloseTo(3, 1);
    expect(groupNearby([at('a', 0), at('d', 10)])).toEqual([]);
  });

  it('ตัวเลขเทียบที่พักนับจาก counts/sources ไม่มีข้อมูลเป็น 0', () => {
    expect(compareCounts({ counts: { attraction: 4, cafe: 9 }, sources: { verified: 1 }, total: 13 })).toEqual({ attraction: 4, cafe: 9, verified: 1, total: 13 });
    expect(compareCounts(null)).toEqual({ attraction: 0, cafe: 0, verified: 0, total: 0 });
  });
});
