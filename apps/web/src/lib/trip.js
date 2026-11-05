// ทริปจากสถานที่โปรด: เรียงจุด จับกลุ่มที่อยู่ใกล้กัน หาจุดถัดไป และจำจุดที่ไปแล้วในเครื่อง
// ระยะทั้งหมดเป็นเส้นตรง (haversine) ไม่ใช่ระยะขับรถ
import { haversineKm } from './geo.js';

const round2 = (x) => Math.round(x * 100) / 100;
const valid = (p) => p && Number.isFinite(p.lat) && Number.isFinite(p.lon);

// เรียงใกล้ไปไกลจากที่พัก ไม่มีที่พักคงลำดับเดิม (distance_km = null)
export function orderStops(places, stay) {
  const list = (places ?? []).filter(valid);
  if (!valid(stay)) return list.map((p) => ({ ...p, distance_km: null }));
  return list.map((p) => ({ ...p, distance_km: round2(haversineKm(stay, p)) }))
    .sort((a, b) => a.distance_km - b.distance_km);
}

// จุดถัดไป = จุดแรกตามลำดับที่ยังไม่ได้ติ๊กว่าไปแล้ว
export const nextStop = (stops, done) => stops.find((p) => !done.has(p.id)) ?? null;

// จับกลุ่มแบบต่อกันเป็นสาย: สองจุดห่างกันไม่เกิน maxKm อยู่กลุ่มเดียวกัน คืนเฉพาะกลุ่มที่มีตั้งแต่ 2 จุด
// ชื่อกลุ่มใช้สถานที่ที่ตรวจที่มาแล้วในกลุ่ม ไม่มีก็ใช้ชื่อจุดแรก (หน้าเว็บเติมคำว่า "แถว")
export function groupNearby(places, maxKm = 2) {
  const list = (places ?? []).filter(valid);
  const parent = list.map((_, i) => i);
  const find = (i) => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  for (let i = 0; i < list.length; i += 1) {
    for (let j = i + 1; j < list.length; j += 1) {
      if (haversineKm(list[i], list[j]) <= maxKm) parent[find(i)] = find(j);
    }
  }
  const groups = new Map();
  list.forEach((p, i) => {
    const r = find(i);
    if (!groups.has(r)) groups.set(r, []);
    groups.get(r).push(p);
  });
  return [...groups.values()].filter((g) => g.length >= 2).map((items) => {
    let span = 0;
    for (let i = 0; i < items.length; i += 1) for (let j = i + 1; j < items.length; j += 1) span = Math.max(span, haversineKm(items[i], items[j]));
    const named = items.find((p) => p.source === 'verified') ?? items[0];
    return { anchor: named, items, span_km: round2(span) };
  });
}

// จุดที่ไปแล้ว เก็บใน localStorage ของเครื่องนี้ แยกตามผู้ใช้ (ไม่ส่งขึ้นเซิร์ฟเวอร์)
const doneKey = (userId) => `nongtrip-trip-done-${userId}`;
export function loadDone(userId) {
  try { return new Set(JSON.parse(localStorage.getItem(doneKey(userId)) || '[]')); } catch { return new Set(); }
}
export function saveDone(userId, done) {
  try { localStorage.setItem(doneKey(userId), JSON.stringify([...done])); } catch { /* เก็บไม่ได้ก็ใช้ในหน้านี้ต่อ */ }
}

// เทียบที่พัก: ตัวเลขจาก /api/places/nearby รัศมี 5 กม. นับอย่างเดียว ไม่จัดอันดับ
export const COMPARE_RADIUS_KM = 5;
export const compareCounts = (res) => ({
  attraction: res?.counts?.attraction ?? 0,
  cafe: res?.counts?.cafe ?? 0,
  verified: res?.sources?.verified ?? 0,
  total: res?.total ?? 0,
});
