// แชตแบบสตรีม (CONTRACT ข้อ 3.2) อ่าน Server-Sent Events จาก POST /api/chat
import { ApiError, ApiUnavailable, errorFromBody } from './api.js';

// event ที่หน้าเว็บรู้จัก ตัวอื่นข้ามไป (ลูกค้าที่ไม่รู้จัก event ต้องข้ามได้ ตาม v0.13)
export const KNOWN_EVENTS = new Set(['tool', 'places', 'lodgings', 'sources', 'token', 'done', 'error']);

// ตัดข้อความสตรีมเป็นก้อน event คืน [events ที่ครบแล้ว, เศษที่ยังไม่ครบ]
export function parseSSE(buffer) {
  const events = [];
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop();
  for (const block of blocks) {
    let event = 'message';
    const data = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
    }
    if (!data.length) continue;
    try {
      events.push({ event, data: JSON.parse(data.join('\n')) });
    } catch {
      // ก้อนที่อ่านไม่ได้ข้ามไป ไม่ทำให้ทั้งแชตพัง
    }
  }
  return [events, rest];
}

// ป้ายสัญญาอนุญาตของแหล่งที่มา ใช้ค่าจาก license ถ้ามี
export function licenseLabel(src) {
  if (src?.license) return src.license;
  if (String(src?.url ?? '').includes('openstreetmap.org')) return '© OpenStreetMap contributors (ODbL)';
  return null;
}

// ลิงก์ที่มาใช้ได้เฉพาะ http:// หรือ https:// กันลิงก์แบบ javascript: หรือ data:
export function safeUrl(url) {
  return typeof url === 'string' && /^https?:\/\//i.test(url.trim()) ? url.trim() : null;
}

// เปลี่ยนรหัสที่มา [k:...] ในข้อความเป็นเลข [1] [2] ตามลำดับรายการ sources
export function numberCitations(text, sources) {
  if (!sources?.length) return text.replace(/\s?\[k:[^\]]+\]/g, '');
  const idx = new Map(sources.map((s, i) => [s.id, i + 1]));
  return text.replace(/\s?\[k:([^\]]+)\]/g, (m, id) => {
    const n = idx.get(`k:${id}`) ?? idx.get(id);
    return n ? ` [${n}]` : '';
  });
}

// ส่งข้อความแล้วเรียก onEvent(event, data) ทีละขั้น จบเมื่อได้ done หรือ error
export async function sendChat({ message, context, chat_id, last_province, lang, edit_from, history }, onEvent, signal) {
  let res;
  try {
    res = await fetch('/api/chat', {
      method: 'POST',
      credentials: 'include',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify({
        message,
        ...(context ? { context } : {}),
        ...(chat_id ? { chat_id } : {}),
        // จังหวัดที่ถามไว้ล่าสุด ให้ "แล้วคาเฟ่ล่ะ" ตอบต่อได้ (ใช้เมื่อไม่มีหมุด)
        ...(last_province && !context ? { last_province } : {}),
        ...(lang === 'en' ? { lang } : {}),
        // แก้คำถาม/ถามใหม่: ลบตั้งแต่ข้อความนี้ลงไปในแชตที่บันทึกไว้ แล้วถามใหม่ (ต้องมี chat_id)
        ...(edit_from && chat_id ? { edit_from } : {}),
        // บทสนทนาก่อนหน้า (v0.24) ให้บอทเข้าใจคำถามต่อเนื่อง เช่น "ที่นั่น" "เล่าเพิ่มหน่อย"
        ...(history?.length ? { history } : {}),
      }),
      signal,
    });
  } catch (e) {
    if (e?.name === 'AbortError') throw e;
    throw new ApiUnavailable('เชื่อมต่อระบบไม่ได้ ลองใหม่อีกครั้ง');
  }
  const ct = res.headers.get('content-type') ?? '';
  if (!res.ok || !ct.includes('text/event-stream')) {
    if (ct.includes('application/json')) throw errorFromBody(await res.json(), res.status);
    throw new ApiUnavailable('ระบบแชตยังไม่เปิดใช้');
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const [events, rest] = parseSSE(buf);
    buf = rest;
    for (const { event, data } of events) {
      if (!KNOWN_EVENTS.has(event)) continue;
      if (event === 'error') throw new ApiError(data.error ?? 'ระบบขัดข้องชั่วคราว ลองใหม่อีกครั้ง', 200, data.code ?? null);
      onEvent(event, data);
      if (event === 'done') return;
    }
  }
}
