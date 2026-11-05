// ข้อความคำตอบของแชต: แปลง **ตัวหนา** ของโมเดลภาษาเป็นชิ้นส่วนให้หน้าเว็บแสดงตัวหนา ไม่โชว์เครื่องหมาย ** ให้ผู้ใช้เห็น
// ระหว่างพิมพ์ทีละตัวอาจเหลือ ** ที่ยังไม่ปิด ตัดทิ้งไป หัวข้อแบบ markdown (#) ตัดเครื่องหมายออก
// คืน [{ text, bold }] ไม่สร้าง HTML เอง (ข้อความมาจากโมเดล แสดงเป็นข้อความเท่านั้น)
export function richParts(text) {
  const src = String(text ?? '').replace(/^#{1,6}\s+/gm, '');
  const out = [];
  const re = /\*\*([^*\n]+?)\*\*/g;
  let last = 0;
  let m;
  while ((m = re.exec(src))) {
    if (m.index > last) out.push({ text: src.slice(last, m.index), bold: false });
    out.push({ text: m[1], bold: true });
    last = m.index + m[0].length;
  }
  if (last < src.length) out.push({ text: src.slice(last), bold: false });
  return out.map((p) => (p.bold ? p : { ...p, text: p.text.replace(/\*\*/g, '') })).filter((p) => p.text);
}

export const plainText = (text) => richParts(text).map((p) => p.text).join('');
