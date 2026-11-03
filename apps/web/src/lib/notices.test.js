import { describe, expect, it } from 'vitest';
import { noticeText } from './notices.js';

describe('noticeText', () => {
  it('ไทยไม่แปล', () => {
    expect(noticeText('แสดงผลในรัศมี 5 กม. เท่านั้น', 'th')).toBe('แสดงผลในรัศมี 5 กม. เท่านั้น');
    expect(noticeText('แสดงผลในรัศมี 5 กม. เท่านั้น')).toBe('แสดงผลในรัศมี 5 กม. เท่านั้น');
  });
  it('อังกฤษแปลข้อความตายตัวและแบบมีตัวเลข', () => {
    expect(noticeText('พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง', 'en')).toMatch(/^Several stays match/);
    expect(noticeText('พบที่พัก 44 แห่ง แสดง 20 แห่งที่ใกล้หมุดที่สุด', 'en')).toBe('Found 44 stays; showing the 20 nearest to the pin.');
    expect(noticeText('ไม่พบที่พักในรัศมี 5 กม. จึงขยายเป็น 10 กม.', 'en')).toContain('widened to 10 km');
    expect(noticeText('เชื่อมต่อ OpenStreetMap ไม่ได้ในตอนนี้ แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว', 'en')).toBe(
      'Cannot reach OpenStreetMap right now. Only places with a verified source are shown.');
  });
  it('ข้อความที่ไม่รู้จักหรือไม่ใช่สตริงคงเดิม', () => {
    expect(noticeText('ข้อความใหม่', 'en')).toBe('ข้อความใหม่');
    expect(noticeText(undefined, 'en')).toBeUndefined();
  });
});
