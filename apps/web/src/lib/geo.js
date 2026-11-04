// คำนวณระยะและตรวจผลค้นตามกติกาใน docs/CONTRACT.md
export const MAX_RADIUS_KM = 30;

export function haversineKm(a, b) {
  const R = 6371;
  const toRad = (d) => (d * Math.PI) / 180;
  const dLat = toRad(b.lat - a.lat);
  const dLon = toRad(b.lon - a.lon);
  const h =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(a.lat)) * Math.cos(toRad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

// ค้นสถานที่รอบจุด: บังคับรัศมีไม่เกิน 30 กม. ในโค้ด เรียงใกล้ไปไกล
export function placesAround(origin, places, radiusKm = MAX_RADIUS_KM, subtype = null) {
  const r = Math.min(radiusKm, MAX_RADIUS_KM);
  return places
    .filter((p) => p.lat != null && p.lon != null)
    .filter((p) => !subtype || p.subtype === subtype)
    .map((p) => ({ ...p, distance_km: Math.round(haversineKm(origin, p) * 10) / 10 }))
    .filter((p) => p.distance_km <= r)
    .sort((a, b) => a.distance_km - b.distance_km);
}

// ตัวตรวจผลค้น (แยกจากตัวค้น): ใน 30 กม. เรียงถูก ไม่ซ้ำ
export function validateResults(results) {
  const errors = [];
  const seen = new Set();
  results.forEach((p, i) => {
    if (p.distance_km > MAX_RADIUS_KM) errors.push(`${p.id} เกิน 30 กม.`);
    if (i > 0 && results[i - 1].distance_km > p.distance_km) errors.push(`${p.id} เรียงผิด`);
    if (seen.has(p.id)) errors.push(`${p.id} ซ้ำ`);
    seen.add(p.id);
  });
  return { ok: errors.length === 0, errors };
}

export const mapsDirUrl = (p) =>
  `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lon}`;
export const mapsSearchUrl = (p) =>
  `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.name_th)}`;

// ตัวเลือกรัศมีในหน้าค้นหา (กม. ไม่เกิน MAX_RADIUS_KM) และตัวกรองฝั่งหน้าเว็บจากผลที่ API ส่งมาแล้ว
export const RADIUS_OPTIONS = [30, 5, 10, 15];

export function withinRadius(items, radiusKm) {
  return items.filter((p) => typeof p.distance_km === 'number' && p.distance_km <= radiusKm);
}

// ผลที่โหลดมาเรียงใกล้ไปไกลแล้ว รู้ครบทุกแห่งในรัศมีนี้หรือยัง: โหลดครบทั้งหมด หรือแห่งสุดท้ายที่โหลดอยู่เลยรัศมีไปแล้ว
export function radiusComplete(items, total, radiusKm) {
  if (items.length >= total) return true;
  const last = items[items.length - 1];
  return Boolean(last) && last.distance_km > radiusKm;
}

// กรอบประเทศไทยแบบเดียวกับฝั่ง API (services/places/geo.py THAILAND_BOUNDS) ใช้ตรวจตำแหน่งเครื่องก่อนค้น
export const THAILAND_BOUNDS = [5.4, 20.6, 97.3, 105.7];
export const inThailand = ({ lat, lon }) => lat >= THAILAND_BOUNDS[0] && lat <= THAILAND_BOUNDS[1] && lon >= THAILAND_BOUNDS[2] && lon <= THAILAND_BOUNDS[3];
