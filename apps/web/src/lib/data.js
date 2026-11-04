// สถานที่ที่ตรวจที่มาแล้วจาก services/places/data ใช้แสดงบนหน้าเว็บโดยไม่ต้องรอ API
// รูปแบบตาม docs/CONTRACT.md ข้อ 4: id แบบ v:, kind (attraction/cafe), subtype
import all from '@data/places_all_provinces.json';
import cm from '@data/places.json';

// รหัสในไฟล์ไม่ซ้ำกัน (p01..p24 เชียงใหม่, p101.. จังหวัดอื่น) ใช้เป็นรหัส v: แบบเดียวกับ API
const merged = new Map();
[...cm.places, ...all.places]
  .filter((p) => p.verified)
  .forEach((p) => { if (!merged.has(p.id)) merged.set(p.id, p); });

// ไม่ส่งต่อราคา/ค่าเข้า (CONTRACT ข้อ 1) และแปลง category ในไฟล์เป็น kind + subtype
export const PLACES = [...merged.values()].map(({ cost_thb, category, ...p }) => ({
  ...p,
  id: `v:${p.id}`,
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
export const SUBTYPE_EN = {
  temple: 'Temple', museum: 'Museum', nature: 'Nature', activity: 'Activity', market: 'Market',
  cafe: 'Café', craft: 'Crafts', waterfall: 'Waterfall', viewpoint: 'Viewpoint', beach: 'Beach', park: 'Park',
  attraction: 'Attraction', gallery: 'Gallery', zoo: 'Zoo', theme_park: 'Theme park', aquarium: 'Aquarium',
  monument: 'Monument', castle: 'Old palace', ruins: 'Ruins', archaeological_site: 'Archaeological site',
  fort: 'Old fort', city_gate: 'City gate', peak: 'Peak', hot_spring: 'Hot spring', cave_entrance: 'Cave',
  nature_reserve: 'Nature reserve', place_of_worship: 'Place of worship',
  hotel: 'Hotel', guest_house: 'Guesthouse', hostel: 'Hostel', motel: 'Motel', resort: 'Resort',
  apartment: 'Apartment', chalet: 'Chalet',
};
const KIND_EN = { attraction: 'Attraction', cafe: 'Café', lodging: 'Stay' };
// ไม่รู้จัก subtype ใช้ป้ายของ kind แทน ไม่โชว์คำภาษาอังกฤษดิบให้ผู้ใช้ (lang = 'en' แสดงป้ายอังกฤษ)
export const subtypeLabel = (s, kind, lang = 'th') => lang === 'en'
  ? (SUBTYPE_EN[s] ?? KIND_EN[kind] ?? 'Unknown type')
  : (SUBTYPE_TH[s] ?? KIND_TH[kind] ?? 'ไม่ทราบประเภท');

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

// ชื่อสถานที่ตามภาษา: อังกฤษใช้ name_en ถ้ามี ไม่มีก็ใช้ชื่อไทย
export const placeName = (p, lang = 'th') => (lang === 'en' && p?.name_en) ? p.name_en : p?.name_th;

// ตัวกรองตามความสนใจ (หน้าค้นหา) จัดจาก subtype ของ OSM และสถานที่ที่ตรวจแล้ว คาเฟ่ใช้ตัวกรองประเภทเดิม
// ชื่อกลุ่มตรงกับคำที่แชตเข้าใจ (services/api/chat_rules.py SUBJECT_SUBTYPES) จึงส่งต่อเป็นคำถามให้แชตได้
export const INTERESTS = [
  { id: 'nature', th: 'ธรรมชาติ', en: 'Nature', ask: ['ธรรมชาติใกล้ที่พักมีที่ไหนบ้าง', 'Nature spots near my stay'],
    subtypes: ['nature', 'waterfall', 'peak', 'beach', 'hot_spring', 'cave_entrance', 'park', 'nature_reserve'] },
  { id: 'history', th: 'วัดและประวัติศาสตร์', en: 'Temples & history', ask: ['วัดและโบราณสถานใกล้ที่พัก', 'Temples and historic sites near my stay'],
    subtypes: ['temple', 'place_of_worship', 'monument', 'city_gate', 'museum', 'gallery', 'castle', 'ruins', 'archaeological_site', 'fort', 'craft'] },
  { id: 'viewpoint', th: 'จุดชมวิว', en: 'Viewpoints', ask: ['จุดชมวิวใกล้ที่พักมีที่ไหนบ้าง', 'Viewpoints near my stay'], subtypes: ['viewpoint'] },
  { id: 'market', th: 'ตลาด', en: 'Markets', ask: ['ตลาดใกล้ที่พักมีที่ไหนบ้าง', 'Markets near my stay'], subtypes: ['market'] },
];
export const interestById = (id) => INTERESTS.find((x) => x.id === id) ?? null;
export const matchesInterest = (p, id) => {
  const it = interestById(id);
  return !it || it.subtypes.includes(p.subtype);
};

// วันที่ดึงข้อมูล OSM ที่เก็บไว้ (data_as_of จาก API รูปแบบ YYYY-MM-DD) เป็นข้อความสั้นตามภาษา รูปแบบผิดคืน null
export function dataDateLabel(iso, lang = 'th') {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(iso ?? '')) return null;
  const d = new Date(`${iso}T00:00:00Z`);
  if (Number.isNaN(d.getTime())) return null;
  return d.toLocaleDateString(lang === 'en' ? 'en-GB' : 'th-TH', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
}
