// เส้นชั้นความสูงแบบแผนที่ สำหรับพื้นหลังหน้าเข้าสู่ระบบ/สมัคร
// คำนวณจากสูตรตายตัว ไม่สุ่ม ภาพจึงเหมือนเดิมทุกครั้งที่เปิด และเทสต์ได้

const r2 = (n) => Math.round(n * 10) / 10;

// จุดรอบ "เนิน" หนึ่งชั้น: รัศมีแกว่งด้วยไซน์สองความถี่ให้ดูเป็นภูมิประเทศจริง ไม่กลมเป๊ะ
export function contourPoints(cx, cy, r, k, n = 28, squash = 0.62) {
  const pts = [];
  for (let i = 0; i < n; i++) {
    const a = (i / n) * Math.PI * 2;
    const rr = r * (1 + 0.13 * Math.sin(3 * a + k * 0.9) + 0.07 * Math.cos(5 * a - k * 1.3));
    pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr * squash]);
  }
  return pts;
}

// ต่อจุดเป็นเส้นโค้งปิดแบบ Catmull-Rom แปลงเป็น cubic Bézier (เส้นนุ่ม ไม่มีมุม)
export function smoothClosedPath(pts) {
  const n = pts.length;
  if (n < 3) return '';
  const p = (i) => pts[(i + n) % n];
  let d = `M${r2(p(0)[0])},${r2(p(0)[1])}`;
  for (let i = 0; i < n; i++) {
    const [p0, p1, p2, p3] = [p(i - 1), p(i), p(i + 1), p(i + 2)];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${r2(c1[0])},${r2(c1[1])} ${r2(c2[0])},${r2(c2[1])} ${r2(p2[0])},${r2(p2[1])}`;
  }
  return `${d}Z`;
}

// ชุดเนินทั้งหมด: [จุดกลาง x, y, รัศมีเริ่ม, จำนวนชั้น]
export const HILLS = [[140, 560, 46, 5], [600, 430, 40, 6], [470, 760, 34, 4]];

export function contours(hills = HILLS, gap = 30) {
  const out = [];
  hills.forEach(([cx, cy, r0, layers], h) => {
    for (let k = 0; k < layers; k++) out.push(smoothClosedPath(contourPoints(cx, cy, r0 + k * gap, k + h * 2)));
  });
  return out;
}

// เส้นทางทริปจากที่พักไปแวะที่เที่ยว (พิกัดใน viewBox 720x1000) จุดหมุดต้องอยู่บนเส้นนี้
export const STOPS = {
  stay: [360, 912], cafe: [96, 842], temple: [132, 628], mountain: [592, 520], beach: [628, 790],
};
export const ROUTE = 'M360,912 C270,918 150,906 96,842 S70,690 132,628 S392,470 592,520 S712,712 628,790';
