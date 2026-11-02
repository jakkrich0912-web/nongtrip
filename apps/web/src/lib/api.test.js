import { describe, it, expect, vi, afterEach } from 'vitest';
import { errorFromBody, lodgingsSearch } from './api.js';

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

describe('lodgingsSearch', () => {
  afterEach(() => vi.unstubAllGlobals());
  const stub = () => {
    const calls = [];
    vi.stubGlobal('fetch', async (url) => {
      calls.push(url);
      return { ok: true, status: 200, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({ items: [] }) };
    });
    return calls;
  };
  it('ส่งเฉพาะตัวกรองที่กรอก', async () => {
    const calls = stub();
    await lodgingsSearch({ q: 'October Hostel', province: 'เชียงใหม่', area: '', subtype: '' });
    const u = new URL(calls[0], 'http://x');
    expect(u.pathname).toBe('/api/lodgings/search');
    expect(u.searchParams.get('q')).toBe('October Hostel');
    expect(u.searchParams.get('province')).toBe('เชียงใหม่');
    expect(u.searchParams.has('area')).toBe(false);
    expect(u.searchParams.has('subtype')).toBe(false);
  });
  it('ส่งย่านและประเภทเมื่อกรอก', async () => {
    const calls = stub();
    await lodgingsSearch({ q: 'hostel', area: 'นิมมาน', subtype: 'hostel' });
    const u = new URL(calls[0], 'http://x');
    expect(u.searchParams.get('area')).toBe('นิมมาน');
    expect(u.searchParams.get('subtype')).toBe('hostel');
  });
});
