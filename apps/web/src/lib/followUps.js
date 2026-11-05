// ปุ่มถามต่อใต้คำตอบล่าสุดของน้องทริป: เลือกตามชนิดคำตอบ กดแล้วส่งเป็นคำถามถัดไปทันที
// บอทเข้าใจคำถามต่อเนื่องจาก history, last_province และหมุดที่เลือกไว้ จึงไม่ต้องใส่ชื่อที่ซ้ำในปุ่ม
// คืน [[ไทย, อังกฤษ], ...] ไม่เกิน 4 ปุ่ม คำตอบที่ยังไม่จบ ถามกลับว่าแถวไหน หรือให้เลือกที่พัก ไม่มีปุ่ม
export const MAX_FOLLOW_UPS = 4;

export function followUps(message) {
  if (!message || message.role !== 'bot' || message.status !== 'done' || !message.text) return [];
  if (message.ask === 'location' || message.lodgings?.items?.length) return [];
  const items = message.places?.items ?? [];
  if (!items.length) return [];
  const out = [];
  const knowledge = Boolean(message.sources?.length);
  if (knowledge) out.push(['เล่าเพิ่ม', 'Tell me more']);
  const cafesOnly = items.every((p) => p.kind === 'cafe');
  const attractionsOnly = items.every((p) => p.kind !== 'cafe');
  if (cafesOnly) out.push(['ที่เที่ยวแถวนี้', 'Attractions nearby']);
  else if (attractionsOnly) out.push(['คาเฟ่แถวนี้', 'Cafés nearby']);
  // ขอดูเพิ่มโดยระบุประเภทเดิม ไม่ให้ผลรอบถัดไปปนคาเฟ่กับที่เที่ยว
  if ((message.places?.total ?? items.length) > items.length) {
    if (cafesOnly) out.push(['ขอดูคาเฟ่ 10 แห่ง', 'Show 10 cafés']);
    else if (attractionsOnly) out.push(['ขอดูที่เที่ยว 10 แห่ง', 'Show 10 attractions']);
    else out.push(['ขอดู 10 แห่ง', 'Show 10 places']);
  }
  out.push(['ที่พักใกล้ ๆ', 'Places to stay nearby']);
  // ถามช่วงเวลาได้เฉพาะคำตอบที่อ้างคลังความรู้ (มีข้อมูลสถานที่นั้น) รายชื่อล้วนไม่มีข้อมูลฤดูกาล
  if (knowledge) out.push(['ไปช่วงไหนดี', 'When is a good time to go?']);
  return out.slice(0, MAX_FOLLOW_UPS);
}
