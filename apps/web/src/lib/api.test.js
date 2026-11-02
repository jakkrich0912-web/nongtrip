import { describe, it, expect } from 'vitest';
import { errorFromBody } from './api.js';

describe('errorFromBody', () => {
  it('ใช้ข้อความในฟิลด์ error และเก็บ code', () => {
    const e = errorFromBody({ error: 'lat ต้องอยู่ในประเทศไทย', code: 'invalid_param' }, 400);
    expect(e.message).toBe('lat ต้องอยู่ในประเทศไทย');
    expect(e.code).toBe('invalid_param');
    expect(e.status).toBe(400);
  });
  it('ไม่มี code ก็อ่านได้ (endpoint ค้นหาส่งแค่ error)', () => {
    expect(errorFromBody({ error: 'ไม่พบ' }, 404).code).toBeNull();
  });
  it('คำตอบไม่มี error ใช้ข้อความกลาง ไม่โชว์รหัส HTTP', () => {
    const e = errorFromBody({}, 500);
    expect(e.message).not.toMatch(/500|HTTP/);
  });
});
