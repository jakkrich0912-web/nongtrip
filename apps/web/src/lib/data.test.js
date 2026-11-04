import { describe, expect, it } from 'vitest';
import { placeName, subtypeLabel } from './data.js';

describe('ป้ายตามภาษา', () => {
  it('subtypeLabel ไทยเป็นค่าเริ่มต้น อังกฤษเมื่อขอ', () => {
    expect(subtypeLabel('temple', 'attraction')).toBe('วัด');
    expect(subtypeLabel('temple', 'attraction', 'en')).toBe('Temple');
  });
  it('subtype ที่ไม่รู้จักใช้ป้ายของ kind ไม่โชว์คำดิบ', () => {
    expect(subtypeLabel('zzz', 'cafe')).toBe('คาเฟ่');
    expect(subtypeLabel('zzz', 'cafe', 'en')).toBe('Café');
    expect(subtypeLabel(undefined, undefined, 'en')).toBe('Unknown type');
  });
  it('placeName อังกฤษใช้ name_en ถ้ามี ไม่มีก็ใช้ชื่อไทย', () => {
    const p = { name_th: 'วัดภูมินทร์', name_en: 'Wat Phumin' };
    expect(placeName(p, 'th')).toBe('วัดภูมินทร์');
    expect(placeName(p, 'en')).toBe('Wat Phumin');
    expect(placeName({ name_th: 'วัดน้อย', name_en: null }, 'en')).toBe('วัดน้อย');
  });
});
