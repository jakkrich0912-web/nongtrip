import { describe, expect, it } from 'vitest';
import { recentStays } from './recent.js';

describe('ค้นล่าสุดในหน้าแรก', () => {
  it('ไม่เกิน 3 รายการ ชื่อซ้ำเหลือครั้งล่าสุด ข้อมูลไม่ครบตัดทิ้ง', () => {
    const items = [
      { id: 5, name: 'บ้านริมน้ำ', lat: 18.7, lon: 98.9 },
      { id: 4, name: 'บ้านริมน้ำ ', lat: 18.7, lon: 98.9 },
      { id: 3, name: 'โรงแรมเอ', lat: null, lon: 98.9 },
      { id: 2, name: 'โฮสเทลบี', lat: 13.7, lon: 100.5 },
      { id: 1, name: 'รีสอร์ตซี', lat: 7.9, lon: 98.3 },
      { id: 0, name: 'เกสต์เฮาส์ดี', lat: 12.5, lon: 99.9 },
    ];
    expect(recentStays(items).map((s) => s.id)).toEqual([5, 2, 1]);
    expect(recentStays(null)).toEqual([]);
  });
});
