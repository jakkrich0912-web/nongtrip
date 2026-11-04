import { describe, expect, it, vi } from 'vitest';
import { licenseLabel, numberCitations, parseSSE, safeUrl, sendChat } from './chat.js';

describe('parseSSE', () => {
  it('แยก event ที่ครบ และเก็บเศษที่ยังไม่ครบไว้', () => {
    const [ev, rest] = parseSSE('event: token\ndata: {"text":"ก\\n"}\n\nevent: done\ndata: {"chat_id"');
    expect(ev).toEqual([{ event: 'token', data: { text: 'ก\n' } }]);
    expect(rest).toBe('event: done\ndata: {"chat_id"');
  });
  it('event ที่ไม่รู้จักก็อ่านได้ (หน้าเว็บค่อยข้ามเอง) และก้อนเสียไม่ทำให้พัง', () => {
    const [ev] = parseSSE('event: future\ndata: {"x":1}\n\nevent: token\ndata: {เสีย\n\n');
    expect(ev).toEqual([{ event: 'future', data: { x: 1 } }]);
  });
  it('รองรับ \\r\\n', () => {
    const [ev] = parseSSE('event: done\r\ndata: {"chat_id":null,"mode":"rule"}\r\n\r\n');
    expect(ev[0].data.chat_id).toBeNull();
  });
});

describe('numberCitations', () => {
  const sources = [{ id: 'k:p101:0' }, { id: 'k:p102:1' }];
  it('เปลี่ยนรหัสที่มาเป็นเลขตามลำดับ', () => {
    expect(numberCitations('วัดสวย [k:p102:1] และเก่า [k:p101:0]', sources)).toBe('วัดสวย [2] และเก่า [1]');
  });
  it('ไม่มี sources (โหมดกฎ) ตัดรหัสทิ้ง ข้อความปกติไม่เปลี่ยน', () => {
    expect(numberCitations('พบ 3 แห่ง', [])).toBe('พบ 3 แห่ง');
    expect(numberCitations('ก [k:x:0]', [])).toBe('ก');
  });
});

describe('licenseLabel', () => {
  it('ใช้ license จากข้อมูล และรู้จัก OSM', () => {
    expect(licenseLabel({ license: 'CC BY-SA 4.0' })).toBe('CC BY-SA 4.0');
    expect(licenseLabel({ url: 'https://www.openstreetmap.org/node/1' })).toBe('© OpenStreetMap contributors (ODbL)');
    expect(licenseLabel({ url: 'https://example.com' })).toBeNull();
  });
});

describe('safeUrl', () => {
  it('รับเฉพาะ http และ https', () => {
    expect(safeUrl('https://th.wikipedia.org/wiki/x')).toBe('https://th.wikipedia.org/wiki/x');
    expect(safeUrl('HTTP://example.com')).toBe('HTTP://example.com');
    expect(safeUrl('javascript:alert(1)')).toBeNull();
    expect(safeUrl('data:text/html,x')).toBeNull();
    expect(safeUrl('//evil.example')).toBeNull();
    expect(safeUrl(null)).toBeNull();
  });
});

describe('sendChat body', () => {
  const body = async (args) => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: new Headers({ 'content-type': 'text/event-stream' }),
      body: { getReader: () => ({ read: async () => ({ done: true }) }) },
    });
    vi.stubGlobal('fetch', fetchMock);
    await sendChat(args, () => {});
    vi.unstubAllGlobals();
    return JSON.parse(fetchMock.mock.calls[0][1].body);
  };
  it('ส่งจังหวัดล่าสุดเมื่อไม่มีหมุด และส่ง lang เฉพาะอังกฤษ', async () => {
    expect(await body({ message: 'a', last_province: 'น่าน', lang: 'en' })).toEqual({ message: 'a', last_province: 'น่าน', lang: 'en' });
    expect(await body({ message: 'a', last_province: 'น่าน', lang: 'th' })).toEqual({ message: 'a', last_province: 'น่าน' });
  });
  it('มีหมุดแล้วไม่ส่งจังหวัดล่าสุด', async () => {
    const sent = await body({ message: 'a', context: { lat: 1, lon: 2 }, last_province: 'น่าน' });
    expect(sent).toEqual({ message: 'a', context: { lat: 1, lon: 2 } });
  });
});
