import { describe, expect, it } from 'vitest';
import { HILLS, ROUTE, STOPS, contourPoints, contours, smoothClosedPath } from './authScene.js';

describe('พื้นหลังแผนที่ทริป', () => {
  it('เส้นชั้นความสูงเป็นเส้นโค้งปิด จำนวนชั้นตามที่กำหนด', () => {
    const lines = contours();
    expect(lines.length).toBe(HILLS.reduce((n, h) => n + h[3], 0));
    for (const d of lines) {
      expect(d.startsWith('M')).toBe(true);
      expect(d.trim().endsWith('Z')).toBe(true);
      expect(d).not.toMatch(/NaN|Infinity/);
    }
  });

  it('จุดของเส้นชั้นอยู่รอบจุดศูนย์กลาง และเส้นโค้งผ่านทุกจุด', () => {
    const pts = contourPoints(100, 100, 50, 1, 12);
    expect(pts).toHaveLength(12);
    for (const [x, y] of pts) {
      expect(Math.hypot(x - 100, (y - 100) / 0.62)).toBeLessThan(80);
    }
    const d = smoothClosedPath(pts);
    expect((d.match(/C/g) || []).length).toBe(12);
  });

  it('เส้นทางเริ่มที่ที่พักและผ่านจุดเที่ยวทุกจุด', () => {
    const nums = ROUTE.match(/-?\d+(\.\d+)?/g).map(Number);
    const pairs = [];
    for (let i = 0; i < nums.length; i += 2) pairs.push(`${nums[i]},${nums[i + 1]}`);
    expect(pairs[0]).toBe(STOPS.stay.join(','));
    for (const id of ['cafe', 'temple', 'mountain', 'beach']) expect(pairs).toContain(STOPS[id].join(','));
  });
});
