import { describe, expect, it } from 'vitest';
import { INTERESTS, interestById, matchesInterest } from './data.js';
import { inThailand } from './geo.js';
import { chatSuggestions } from './useChatSession.js';

describe('ตัวกรองตามความสนใจ', () => {
  it('จัดกลุ่มจาก subtype ไม่มีกลุ่มไหนซ้ำ subtype กัน', () => {
    const all = INTERESTS.flatMap((x) => x.subtypes);
    expect(new Set(all).size).toBe(all.length);
    expect(matchesInterest({ subtype: 'waterfall' }, 'nature')).toBe(true);
    expect(matchesInterest({ subtype: 'temple' }, 'nature')).toBe(false);
    expect(matchesInterest({ subtype: 'ruins' }, 'history')).toBe(true);
    expect(matchesInterest({ subtype: 'anything' }, '')).toBe(true);
  });

  it('แชตได้คำถามแนะนำตามความสนใจเป็นข้อแรก', () => {
    expect(chatSuggestions(true, interestById('viewpoint'))[0][0]).toBe('จุดชมวิวใกล้ที่พักมีที่ไหนบ้าง');
    expect(chatSuggestions(true, null)[0][0]).toBe('คาเฟ่ใกล้ที่พักมีที่ไหนบ้าง');
    expect(chatSuggestions(false, interestById('viewpoint'))[0][0]).toBe('คาเฟ่ในเชียงใหม่');
  });

  it('ตำแหน่งเครื่องต้องอยู่ในประเทศไทย', () => {
    expect(inThailand({ lat: 13.75, lon: 100.5 })).toBe(true);
    expect(inThailand({ lat: 35.68, lon: 139.69 })).toBe(false);
  });
});

describe('ป้ายความสดของข้อมูล', async () => {
  const { dataDateLabel } = await import('./data.js');
  it('แสดงวันที่ตามภาษา (ไทยเป็น พ.ศ.) และไม่แสดงเมื่อไม่มีวันที่', () => {
    expect(dataDateLabel('2026-11-04', 'th')).toBe('4 พ.ย. 2569');
    expect(dataDateLabel('2026-11-04', 'en')).toBe('4 Nov 2026');
    expect(dataDateLabel(null)).toBe(null);
    expect(dataDateLabel('4/11/2026')).toBe(null);
  });
});
