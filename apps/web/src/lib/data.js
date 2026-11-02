// ข้อมูลจำลองระหว่างรอ services/api: ใช้สถานที่ที่ตรวจที่มาแล้วใน services/places/data
// เมื่อ API พร้อม ให้เปลี่ยนฟังก์ชันในไฟล์นี้ไปเรียก API แทน หน้าเว็บไม่ต้องแก้
import all from '@data/places_all_provinces.json';
import cm from '@data/places.json';

const merged = new Map();
[...cm.places, ...all.places]
  .filter((p) => p.verified)
  .forEach((p) => { if (!merged.has(p.id + p.name_th)) merged.set(p.id + p.name_th, p); });

// ไม่ส่งต่อราคา/ค่าเข้าตาม CONTRACT ข้อ 4
export const PLACES = [...merged.values()].map(({ cost_thb, ...p }, i) => ({ ...p, id: `${p.id}-${i}`, source: 'verified' }));

export const CATEGORY_TH = {
  temple: 'วัด', cafe: 'คาเฟ่', museum: 'พิพิธภัณฑ์', nature: 'ธรรมชาติ',
  activity: 'กิจกรรม', market: 'ตลาด', viewpoint: 'จุดชมวิว', beach: 'ชายหาด',
};
export const categoryLabel = (c) => CATEGORY_TH[c] ?? c ?? 'ไม่ทราบประเภท';
