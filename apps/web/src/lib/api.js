// ตัวเรียก services/api ตาม docs/CONTRACT.md ข้อ 3
// ตอน `npm run dev` Vite ส่งต่อ /api ไปที่ VITE_API_URL (ค่าเริ่มต้น http://localhost:8000)

// เรียก API ไม่ได้เลย (เซิร์ฟเวอร์ไม่เปิด เน็ตหลุด)
export class ApiUnavailable extends Error {}

// API ตอบข้อผิดพลาด: message คือฟิลด์ `error` (ภาษาไทยพร้อมแสดง), code คือฟิลด์ `code` ถ้ามี (ข้อ 3.1)
export class ApiError extends Error {
  constructor(message, status, code = null) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

// อ่านข้อผิดพลาดจากคำตอบ ใช้ข้อความในฟิลด์ error ตรงๆ ไม่แสดงรหัส HTTP หรือชื่อฟิลด์ให้ผู้ใช้เห็น
export function errorFromBody(body, status) {
  const message = typeof body?.error === 'string' && body.error.trim()
    ? body.error
    : 'ระบบขัดข้องชั่วคราว ลองใหม่อีกครั้ง';
  return new ApiError(message, status, typeof body?.code === 'string' ? body.code : null);
}

async function get(path) {
  let res;
  try {
    res = await fetch(path, { credentials: 'include' });
  } catch {
    throw new ApiUnavailable('เชื่อมต่อระบบค้นไม่ได้ ตรวจว่าเปิด services/api อยู่');
  }
  const ct = res.headers.get('content-type') ?? '';
  if (!ct.includes('application/json')) throw new ApiUnavailable('ระบบค้นยังไม่เปิดใช้');
  const body = await res.json();
  if (!res.ok) throw errorFromBody(body, res.status);
  return body;
}

const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v != null && v !== '')).toString();

// ผู้ที่ยังไม่ได้จอง: ที่พักรอบหมุด 5 กม. ขยายเป็น 10 (ข้อ 3 และข้อ 4 คำตอบของ lodgings/near)
export const lodgingsNear = ({ lat, lon }) => get(`/api/lodgings/near?${qs({ lat, lon })}`);

// ค้นที่พักจากชื่อ ตัวกรองไม่บังคับ (CONTRACT v0.11)
export const lodgingsSearch = ({ q, province, area, subtype }) =>
  get(`/api/lodgings/search?${qs({ q, province, area, subtype })}`);

// สถานที่รอบจุด kinds = attraction,cafe
export const placesNearby = ({ lat, lon, radius_km = 30, kinds, limit, offset }) =>
  get(`/api/places/nearby?${qs({ lat, lon, radius_km, kinds, limit, offset })}`);
