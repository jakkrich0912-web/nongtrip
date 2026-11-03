// Notices from the search service are written in Thai. When the site is in English they are translated here.
// Unknown notices are shown as they are, so nothing is ever hidden.
const FIXED = {
  'ค้นรอบจุดกลางจังหวัด ไม่ใช่รอบที่พักของคุณ ปักหมุดที่พักเพื่อให้ตรงขึ้น': 'Searched around the province centre, not your stay. Pin your stay for a closer result.',
  'พบหลายรายการ กรุณาเลือกที่พักที่ตรงกับที่จอง': 'Several stays match. Please choose the one you booked.',
  'ไม่พบที่พักที่ตรงตัวกรอง ลองเอาตัวกรองออกบางข้อ หรือปักหมุดบนแผนที่': 'No stay matches the filters. Try removing some filters or pin the map.',
  'ไม่พบที่พักชื่อนี้ ลองพิมพ์ชื่ออื่น หรือปักหมุดบนแผนที่': 'No stay with this name. Try another name or pin the map.',
  'ข้อมูลที่บันทึกไว้ยังกรองตามย่านไม่ได้ ผลที่เห็นไม่ได้ถูกกรองด้วยย่าน': 'Saved data cannot be filtered by area yet, so the results are not filtered by area.',
  'ผลค้นนี้ไม่ผ่านการตรวจอิสระ โปรดอย่าเชื่อถือจนกว่าจะตรวจสอบ': 'These results failed the independent check. Please do not rely on them until verified.',
  'ระยะเป็นเส้นตรง ไม่ใช่ระยะขับรถ': 'Distances are straight-line, not driving distances.',
};
const REASONS = {
  'ปิดการค้นหาจาก OpenStreetMap อยู่': 'OpenStreetMap search is switched off.',
  'ค้นชื่อที่พักออนไลน์ไม่ได้ในตอนนี้': 'Cannot search stay names online right now.',
  'เชื่อมต่อ OpenStreetMap ไม่ได้ในตอนนี้': 'Cannot reach OpenStreetMap right now.',
  'ดึงข้อมูลจาก OpenStreetMap ไม่สำเร็จ': 'Could not fetch data from OpenStreetMap.',
};
const PATTERNS = [
  [/^ค้นได้ไกลสุด ([\d.]+) กม\. จึงใช้ ([\d.]+) กม\. แทน$/, (a, b) => `The maximum search radius is ${a} km, so ${b} km was used.`],
  [/^แสดงได้ครั้งละไม่เกิน (\d+) แห่ง$/, (a) => `At most ${a} places are shown at a time.`],
  [/^แสดงผลในรัศมี ([\d.]+) กม\. เท่านั้น$/, (a) => `Results are shown within ${a} km only.`],
  [/^ไม่พบที่พักในรัศมี ([\d.]+) กม\. จึงขยายเป็น ([\d.]+) กม\.$/, (a, b) => `No stays within ${a} km, so the search was widened to ${b} km.`],
  [/^ไม่พบที่พักในรัศมี ([\d.]+) กม\. จากหมุดนี้$/, (a) => `No stays within ${a} km of this pin.`],
  [/^พบที่พัก (\d+) แห่ง แสดง (\d+) แห่งที่ใกล้หมุดที่สุด$/, (a, b) => `Found ${a} stays; showing the ${b} nearest to the pin.`],
  [/^พื้นที่หนาแน่นมาก ข้อมูลจาก OpenStreetMap จึงครอบคลุมแค่ ([\d.]+) กม\.$/, (a) => `This area is very dense, so OpenStreetMap data covers only ${a} km.`],
  [/^(.+) แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว$/, (r) => `${REASONS[r] ?? r} Only places with a verified source are shown.`],
  [/^(.+) ให้ปักหมุดบนแผนที่แทน$/, (r) => `${REASONS[r] ?? r} Please pin your stay on the map instead.`],
];

export function noticeText(notice, lang = 'th') {
  if (lang !== 'en' || typeof notice !== 'string') return notice;
  if (FIXED[notice]) return FIXED[notice];
  for (const [rx, make] of PATTERNS) {
    const m = notice.match(rx);
    if (m) return make(...m.slice(1));
  }
  return notice;
}
