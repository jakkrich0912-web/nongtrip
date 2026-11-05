// ที่พักที่ค้นล่าสุดสำหรับหน้าแรก: ใหม่สุดก่อน ชื่อซ้ำเอาครั้งล่าสุด ไม่เกิน 3 รายการ ข้อมูลไม่ครบตัดทิ้ง
export const RECENT_LIMIT = 3;

export function recentStays(items, limit = RECENT_LIMIT) {
  const seen = new Set();
  const out = [];
  for (const s of Array.isArray(items) ? items : []) {
    if (!s?.name || !Number.isFinite(s.lat) || !Number.isFinite(s.lon)) continue;
    const key = s.name.trim().toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(s);
    if (out.length >= limit) break;
  }
  return out;
}
