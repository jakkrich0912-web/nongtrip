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

// เรียก API ทุกแบบ ส่งคุกกี้เซสชันไปด้วยเสมอ (ข้อ 3.3) ตอบ 204 คืน null
async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: 'include',
      headers: body === undefined ? undefined : { 'content-type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiUnavailable('เชื่อมต่อระบบไม่ได้ ตรวจว่าเปิด services/api อยู่');
  }
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') ?? '';
  if (!ct.includes('application/json')) throw new ApiUnavailable('ระบบยังไม่เปิดใช้');
  const data = await res.json();
  if (!res.ok) throw errorFromBody(data, res.status);
  return data;
}
const get = (path) => request('GET', path);

const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v != null && v !== '')).toString();

// ผู้ที่ยังไม่ได้จอง: ที่พักรอบหมุด 5 กม. ขยายเป็น 10 (ข้อ 3 และข้อ 4 คำตอบของ lodgings/near)
export const lodgingsNear = ({ lat, lon }) => get(`/api/lodgings/near?${qs({ lat, lon })}`);

// ค้นที่พักจากชื่อ ตัวกรองไม่บังคับ (CONTRACT v0.11)
export const lodgingsSearch = ({ q, province, area, subtype }) =>
  get(`/api/lodgings/search?${qs({ q, province, area, subtype })}`);

// สถานที่รอบจุด kinds = attraction,cafe
export const placesNearby = ({ lat, lon, radius_km = 30, kinds, limit, offset }) =>
  get(`/api/places/nearby?${qs({ lat, lon, radius_km, kinds, limit, offset })}`);

// ผู้ใช้ (ข้อ 3.3)
export const authMe = () => request('GET', '/api/auth/me');
export const authLogin = (email, password) => request('POST', '/api/auth/login', { email, password });
export const authRegister = (email, password) => request('POST', '/api/auth/register', { email, password });
export const authLogout = () => request('POST', '/api/auth/logout');
export const deleteAccount = (email) => request('POST', '/api/me/delete', { email });

// ประวัติ สถานที่โปรด แชต (ข้อ 3.4 ต้องล็อกอิน)
export const mySearches = () => request('GET', '/api/me/searches');
export const saveSearch = ({ name, lat, lon }) => request('POST', '/api/me/searches', { name, lat, lon });
export const deleteSearch = (id) => request('DELETE', `/api/me/searches/${encodeURIComponent(id)}`);
export const deleteAllSearches = () => request('DELETE', '/api/me/searches');

export const myFavorites = () => request('GET', '/api/me/favorites');
// v: ระบบอ่านข้อมูลจากไฟล์เอง ส่งแค่รหัส, osm: ต้องส่งชื่อ พิกัด และ kind ไปด้วย
export const addFavorite = (p) => request('POST', '/api/me/favorites', String(p.id).startsWith('v:')
  ? { place_id: p.id }
  : { place_id: p.id, name_th: p.name_th, lat: p.lat, lon: p.lon, kind: p.kind, subtype: p.subtype ?? null, province: p.province ?? null });
// place_id มี / ได้ (osm:node/123) ส่งเป็นเส้นทางตรงๆ ตามสัญญา
export const removeFavorite = (id) => request('DELETE', `/api/me/favorites/${String(id).split('/').map(encodeURIComponent).join('/')}`);
export const deleteAllFavorites = () => request('DELETE', '/api/me/favorites');

export const myChats = () => request('GET', '/api/me/chats');
export const deleteChat = (id) => request('DELETE', `/api/me/chats/${encodeURIComponent(id)}`);
export const deleteAllChats = () => request('DELETE', '/api/me/chats');

// ไกด์ที่เที่ยว (ข้อ 3.5 ไม่ต้องล็อกอิน)
export const placeById = (id) => request('GET', `/api/places/${encodeURIComponent(id)}`);
export const provincePlaces = (name, { category, limit = 50, offset = 0 } = {}) =>
  request('GET', `/api/provinces/${encodeURIComponent(name)}/places?${qs({ category, limit, offset })}`);
export const provinceCenter = (name) => request('GET', `/api/provinces/${encodeURIComponent(name)}/center`);
export const guideFeatured = ({ limit = 12, category } = {}) => request('GET', `/api/guide/featured?${qs({ limit, category })}`);
