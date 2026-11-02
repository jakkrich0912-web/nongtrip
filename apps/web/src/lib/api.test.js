import { describe, it, expect, vi, afterEach } from 'vitest';
import { errorFromBody, lodgingsSearch, addFavorite, removeFavorite, mySearches, ApiError } from './api.js';

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

describe('สถานที่โปรด', () => {
  afterEach(() => vi.unstubAllGlobals());
  const stub = (status = 201) => {
    const calls = [];
    vi.stubGlobal('fetch', async (url, init) => {
      calls.push({ url, init });
      return { ok: true, status, headers: new Headers({ 'content-type': 'application/json' }), json: async () => ({}) };
    });
    return calls;
  };
  it('สถานที่ v: ส่งแค่รหัส ไม่ส่งชื่อหรือพิกัด', async () => {
    const calls = stub();
    await addFavorite({ id: 'v:p01', name_th: 'วัด', lat: 1, lon: 2, kind: 'attraction' });
    expect(JSON.parse(calls[0].init.body)).toEqual({ place_id: 'v:p01' });
    expect(calls[0].init.credentials).toBe('include');
  });
  it('สถานที่ osm: ส่งชื่อ พิกัด และ kind', async () => {
    const calls = stub();
    await addFavorite({ id: 'osm:node/1', name_th: 'คาเฟ่', lat: 18.7, lon: 98.9, kind: 'cafe', subtype: 'cafe' });
    const b = JSON.parse(calls[0].init.body);
    expect(b).toMatchObject({ place_id: 'osm:node/1', name_th: 'คาเฟ่', lat: 18.7, lon: 98.9, kind: 'cafe' });
  });
  it('ลบรหัสที่มี / ได้', async () => {
    const calls = stub(204);
    const r = await removeFavorite('osm:node/123');
    expect(calls[0].url).toBe('/api/me/favorites/osm%3Anode/123');
    expect(calls[0].init.method).toBe('DELETE');
    expect(r).toBeNull();
  });
});

describe('session หมดอายุ', () => {
  afterEach(() => vi.unstubAllGlobals());
  it('request() ได้ 401 โยน ApiError ที่มี status 401 และ code ให้หน้าจอเช็กได้', async () => {
    vi.stubGlobal('fetch', async () => ({
      ok: false, status: 401, headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => ({ error: 'กรุณาเข้าสู่ระบบก่อน', code: 'unauthorized' }),
    }));
    const err = await mySearches().catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(401);
    expect(err.code).toBe('unauthorized');
    expect(err.message).toBe('กรุณาเข้าสู่ระบบก่อน');
  });
});
