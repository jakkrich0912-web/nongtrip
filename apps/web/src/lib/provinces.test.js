import { describe, expect, it } from 'vitest';
import { PROVINCES, PROVINCE_EN, REGION_EN, provinceLabel, regionLabel, matchProvince } from './provinces.js';

describe('province names', () => {
  it('has an English name for every one of the 77 provinces and nothing extra', () => {
    expect(PROVINCES).toHaveLength(77);
    expect(Object.keys(PROVINCE_EN).sort()).toEqual([...PROVINCES].sort());
    expect(new Set(Object.values(PROVINCE_EN)).size).toBe(77);
  });
  it('labels follow the chosen language and fall back to the given name', () => {
    expect(provinceLabel('เชียงใหม่', 'en')).toBe('Chiang Mai');
    expect(provinceLabel('เชียงใหม่', 'th')).toBe('เชียงใหม่');
    expect(provinceLabel('ไม่มีจังหวัดนี้', 'en')).toBe('ไม่มีจังหวัดนี้');
    expect(regionLabel('ใต้', 'en')).toBe('South region');
    expect(regionLabel('ใต้', 'th')).toBe('ภาคใต้');
    expect(Object.keys(REGION_EN)).toHaveLength(6);
  });
  it('matches Thai or English text, ignoring case and spaces', () => {
    expect(matchProvince('เชียงใหม่', 'เชียง')).toBe(true);
    expect(matchProvince('เชียงใหม่', 'chiang mai')).toBe(true);
    expect(matchProvince('เชียงใหม่', 'CHIANGMAI')).toBe(true);
    expect(matchProvince('เชียงใหม่', 'ภูเก็ต')).toBe(false);
    expect(matchProvince('เชียงใหม่', '  ')).toBe(true);
  });
});
