import { describe, expect, it } from 'vitest';
import { plainText, richParts } from './richText.js';

describe('ตัวหนาในคำตอบแชต', () => {
  it('แปลง **ชื่อ** เป็นตัวหนา และไม่เหลือเครื่องหมาย', () => {
    expect(richParts('1. **วัดร่องขุ่น** (เชียงราย)')).toEqual([
      { text: '1. ', bold: false }, { text: 'วัดร่องขุ่น', bold: true }, { text: ' (เชียงราย)', bold: false },
    ]);
  });
  it('** ที่ยังไม่ปิดระหว่างพิมพ์ และหัวข้อ # ไม่โชว์', () => {
    expect(plainText('2. **ศูนย์ศึกษ')).toBe('2. ศูนย์ศึกษ');
    expect(plainText('## แผนวันที่ 1\nเที่ยว')).toBe('แผนวันที่ 1\nเที่ยว');
    expect(richParts('')).toEqual([]);
  });
});
