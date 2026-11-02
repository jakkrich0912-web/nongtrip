// ตัวเรียก services/api ตาม docs/CONTRACT.md ข้อ 3
// ตอนพัฒนา Vite ส่งต่อ /api ไปที่ VITE_API_URL (ค่าเริ่มต้น http://localhost:8000)
export class ApiUnavailable extends Error {}

async function get(path) {
  let res;
  try {
    res = await fetch(path, { credentials: 'include' });
  } catch {
    throw new ApiUnavailable('เชื่อมต่อระบบค้นไม่ได้');
  }
  const ct = res.headers.get('content-type') ?? '';
  if (!ct.includes('application/json')) throw new ApiUnavailable('ระบบค้นยังไม่เปิดใช้');
  const body = await res.json();
  if (!res.ok) throw new Error(body.message ?? body.error ?? `HTTP ${res.status}`);
  return body;
}

export const lodgingNearby = ({ lat, lon, preview = 3 }) =>
  get(`/api/lodging/nearby?lat=${lat}&lon=${lon}&preview=${preview}`);
