// ท่าทางเองของน้องทริปบนเวที (หน้าเข้าสู่ระบบ/สมัคร): เดินเตาะแตะไปมา กระโดดดึ๋ง ชะโงกดู และยืนหายใจ
// ฟังก์ชันในไฟล์นี้ไม่แตะ DOM เลย ส่งค่าสุ่ม (0..1) เข้ามาเองได้ จึงเทสต์ได้ตรง ๆ
// ท่า walk hop look tail มีภาพเคลื่อนไหวทีละเฟรม (lib/mascotFrames.js) ไฟล์นี้บอกแค่ท่า ระยะ ทิศ และเวลา

export const SPEED = 120;            // พิกเซลต่อวินาทีตอนเดิน
export const STEP_MS = 300;          // หนึ่งก้าว (ตัวเด้งขึ้นลงหนึ่งรอบ)
export const MIN_WALK = 50;          // เดินน้อยกว่านี้ไม่คุ้ม ยืนเฉย ๆ ดีกว่า
export const HOP_MS = 600;           // hop 6 เฟรม 10 fps
export const PEEK_MS = 1500;
export const LOOK_MS = 1000;         // look-around 6 เฟรม 6 fps หนึ่งรอบ
export const TAIL_MS = 1334;         // tail-wag 4 เฟรม 6 fps สองรอบ

// น้ำหนักของแต่ละท่า รวมกันเท่าไรก็ได้ (คิดเป็นสัดส่วน)
// ท่าพัก look/tail ให้น้ำหนักน้อย ไม่เล่นถี่จนรบกวน
export const WEIGHTS = { walk: 36, hop: 14, peek: 12, look: 8, tail: 7, rest: 23 };

const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));

// ระยะที่เดินไปได้จากกึ่งกลางเวที (ซ้าย/ขวาเท่ากัน) เวทีแคบกว่าตัวก็ยืนนิ่งที่กลาง
export function roam(stageWidth, bodyWidth, margin = 24) {
  return Math.max(0, (stageWidth - bodyWidth) / 2 - margin);
}

// เลือกท่าถัดไปตามน้ำหนัก ใช้ค่าสุ่มก้อนเดียว ท่าเดิมซ้ำติดกันได้ยกเว้น hop (กระโดดติดกันดูวุ่นวาย)
export function pickAct(r, last = null, weights = WEIGHTS) {
  const entries = Object.entries(weights).filter(([k]) => !(k === 'hop' && last === 'hop'));
  const total = entries.reduce((n, [, w]) => n + w, 0);
  let x = clamp(r, 0, 0.999999) * total;
  for (const [k, w] of entries) { if ((x -= w) < 0) return k; }
  return entries[entries.length - 1][0];
}

// จุดหมายของการเดิน: สุ่มในช่วงที่เดินได้ แต่ต้องห่างจากที่เดิมอย่างน้อย MIN_WALK ไม่งั้นคืน null (ไม่เดิน)
export function walkTarget(r, x, range) {
  if (range < MIN_WALK / 2) return null;
  let to = Math.round((clamp(r, 0, 1) * 2 - 1) * range);
  if (Math.abs(to - x) < MIN_WALK) {
    // สุ่มได้ใกล้ที่เดิมเกินไป: ขยับออกไปฝั่งที่ยังมีที่ว่าง ไม่มีที่ทั้งสองฝั่งก็ไม่เดิน
    if (x + MIN_WALK <= range) to = x + MIN_WALK;
    else if (x - MIN_WALK >= -range) to = x - MIN_WALK;
    else return null;
  }
  return to;
}

// เวลาเดินจากระยะ (ไม่เร็วหรือช้าเกินไป) และจำนวนก้าวที่ลงตัวกับเวลา
export function walkPlan(from, to) {
  const dist = Math.abs(to - from);
  const ms = clamp(Math.round((dist / SPEED) * 1000), 700, 3200);
  return { ms, steps: Math.max(2, Math.round(ms / STEP_MS)), dir: to > from ? 1 : -1 };
}

// พักระหว่างท่า 1.6-4.4 วินาที ท่าที่เหนื่อยกว่าพักนานกว่านิดหน่อย
export function restAfter(act, r) {
  const base = act === 'walk' ? 2200 : act === 'hop' ? 1800 : act === 'look' || act === 'tail' ? 2600 : 1600;
  return base + Math.round(clamp(r, 0, 1) * 2200);
}

// ปฏิกิริยาต่อสิ่งที่ผู้ใช้ทำในฟอร์ม: สีหน้า (ชื่อภาพในชุด front) ท่าประกอบ และข้อความในกล่องพูด
export const CUES = {
  email: { face: null, act: 'nod', ms: 900 },
  password: { face: 'shy', act: 'peek', ms: 0 },          // ค้างไว้จนกว่าจะออกจากช่องรหัสผ่าน
  reveal: { face: 'squint', act: 'peek', ms: 0 },
  error: { face: 'ouch', act: 'shake', ms: 1600 },
  success: { face: 'star-eyes', act: 'hop', ms: 1800 },
  travel: { face: 'grin', act: 'run', ms: 900 },
};
export const cueOf = (name) => CUES[name] ?? null;
