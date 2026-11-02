// สถานที่ที่ตรวจที่มาแล้วจาก services/places/data ใช้แสดงบนหน้าเว็บโดยไม่ต้องรอ API
// รูปแบบตาม docs/CONTRACT.md ข้อ 4: id แบบ v:, kind (attraction/cafe), subtype
import all from '@data/places_all_provinces.json';
import cm from '@data/places.json';

const merged = new Map();
[...cm.places, ...all.places]
  .filter((p) => p.verified)
  .forEach((p) => { if (!merged.has(`${p.province}|${p.name_th}`)) merged.set(`${p.province}|${p.name_th}`, p); });

// ไม่ส่งต่อราคา/ค่าเข้า (CONTRACT ข้อ 1) และแปลง category ในไฟล์เป็น kind + subtype
export const PLACES = [...merged.values()].map(({ cost_thb, category, ...p }, i) => ({
  ...p,
  id: `v:${p.id}-${i}`,
  kind: category === 'cafe' ? 'cafe' : 'attraction',
  subtype: category ?? null,
  source: 'verified',
}));

// ป้ายภาษาไทยของ subtype (หน้าเว็บเป็นคนแปลง ตามข้อ 3.5)
export const SUBTYPE_TH = {
  temple: 'วัด', museum: 'พิพิธภัณฑ์', nature: 'ธรรมชาติ', activity: 'กิจกรรม', market: 'ตลาด',
  cafe: 'คาเฟ่', craft: 'งานฝีมือ', waterfall: 'น้ำตก', viewpoint: 'จุดชมวิว', beach: 'ชายหาด', park: 'สวนสาธารณะ',
  // ประเภทจาก OpenStreetMap (services/places/osm.py)
  attraction: 'จุดท่องเที่ยว', gallery: 'หอศิลป์', zoo: 'สวนสัตว์', theme_park: 'สวนสนุก', aquarium: 'อควาเรียม',
  monument: 'อนุสาวรีย์', castle: 'วังเก่า', ruins: 'โบราณสถาน', archaeological_site: 'แหล่งโบราณคดี',
  fort: 'ป้อมเก่า', city_gate: 'ประตูเมือง', peak: 'ยอดเขา', hot_spring: 'บ่อน้ำร้อน', cave_entrance: 'ถ้ำ',
  nature_reserve: 'เขตอนุรักษ์', place_of_worship: 'ศาสนสถาน',
  // ที่พัก (lodgings/search ตัวกรอง subtype)
  hotel: 'โรงแรม', guest_house: 'เกสต์เฮาส์', hostel: 'โฮสเทล', motel: 'โมเทล', resort: 'รีสอร์ต',
  apartment: 'อพาร์ตเมนต์', chalet: 'บ้านพัก',
};
const KIND_TH = { attraction: 'ที่เที่ยว', cafe: 'คาเฟ่', lodging: 'ที่พัก' };
// ไม่รู้จัก subtype ใช้ป้ายของ kind แทน ไม่โชว์คำภาษาอังกฤษดิบให้ผู้ใช้
export const subtypeLabel = (s, kind) => SUBTYPE_TH[s] ?? KIND_TH[kind] ?? 'ไม่ทราบประเภท';

// กลุ่มไอคอนและสี (มี 6 กลุ่ม) จาก subtype/kind
const GROUP = {
  temple: 'temple', place_of_worship: 'temple', monument: 'temple', city_gate: 'temple',
  museum: 'museum', gallery: 'museum', castle: 'museum', ruins: 'museum', archaeological_site: 'museum', fort: 'museum', craft: 'museum',
  nature: 'nature', waterfall: 'nature', peak: 'nature', beach: 'nature', hot_spring: 'nature', cave_entrance: 'nature',
  park: 'nature', nature_reserve: 'nature', viewpoint: 'nature',
  activity: 'activity', attraction: 'activity', zoo: 'activity', theme_park: 'activity', aquarium: 'activity',
  market: 'market', cafe: 'cafe',
};
export const iconGroup = (p) => GROUP[p.subtype] ?? (p.kind === 'cafe' ? 'cafe' : 'activity');
