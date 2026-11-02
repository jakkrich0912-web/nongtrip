// โหมด "ยังไม่ได้จองที่พัก" ตาม docs/CONTRACT.md ข้อ 3.4
import { haversineKm, placesAround, MAX_RADIUS_KM } from './geo.js';

export const LODGING_START_KM = 5;
export const LODGING_MAX_KM = 10;

// หาที่พักรอบหมุด: เริ่ม 5 กม. ถ้าไม่พบขยายเป็น 10 กม. และบอกผู้ใช้
export function lodgingAround(origin, lodgings) {
  const withDist = lodgings
    .filter((l) => l.lat != null && l.lon != null)
    .map((l) => ({ ...l, distance_km: Math.round(haversineKm(origin, l) * 10) / 10 }))
    .sort((a, b) => a.distance_km - b.distance_km);
  let radius = LODGING_START_KM;
  let items = withDist.filter((l) => l.distance_km <= radius);
  const notes = [];
  if (items.length === 0) {
    radius = LODGING_MAX_KM;
    items = withDist.filter((l) => l.distance_km <= radius);
    notes.push(`ขยายรัศมีเป็น ${LODGING_MAX_KM} กม. เพราะไม่พบที่พักใน ${LODGING_START_KM} กม.`);
  }
  return { items, meta: { radius_km: radius, notes } };
}

// แนบสถานที่เที่ยวใกล้สุดของแต่ละที่พัก คำนวณในเครื่องจากชุดสถานที่ที่ดึงมาครั้งเดียว
export function attachPreviews(lodgings, places, preview = 3) {
  return lodgings.map((l) => {
    const around = placesAround(l, places, MAX_RADIUS_KM);
    return { ...l, places_preview: around.slice(0, preview), places_total: around.length };
  });
}
