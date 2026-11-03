// น้องทริปเพื่อนคู่ใจ: ตรรกะล้วน ๆ ของมาสคอตที่เดินไปมาทุกหน้าและเปิดหน้าต่างแชตเมื่อกด
// แยกจากหน้าจอเพื่อเทสต์ได้ (ตำแหน่ง เส้นทางเดิน ท่าทางตามสถานะ ตำแหน่งหน้าต่างแชต)

export const COMPANION_SIZE = 88;
export const SPRITE_RATIO = 520 / 373; // ความสูงต่อความกว้างของภาพ front
export const EDGE = 8; // ระยะเว้นจากขอบจอ
export const WALK_SPEED = 64; // พิกเซลต่อวินาที
export const DRAG_THRESHOLD = 6; // ลากเกินนี้ถึงนับเป็นการลาก ไม่ใช่การแตะ
export const NARROW = 560; // จอแคบกว่านี้หน้าต่างแชตเป็นแผ่นเต็มล่างจอ

export const bodyHeight = (size = COMPANION_SIZE) => Math.round(size * SPRITE_RATIO);
const clamp = (n, lo, hi) => Math.min(Math.max(n, lo), Math.max(lo, hi));

// กรอบที่ตัวมาสคอตอยู่ได้ (มุมซ้ายบนของตัว)
export function bounds(vw, vh, size = COMPANION_SIZE) {
  return { minX: EDGE, maxX: Math.max(EDGE, vw - size - EDGE), minY: EDGE, maxY: Math.max(EDGE, vh - bodyHeight(size) - EDGE) };
}

export function clampPos(pos, vw, vh, size = COMPANION_SIZE) {
  const b = bounds(vw, vh, size);
  return { x: clamp(pos.x, b.minX, b.maxX), y: clamp(pos.y, b.minY, b.maxY) };
}

// ตำแหน่งตั้งต้น: มุมล่างขวา ยืนบนขอบล่างจอ
export const homePos = (vw, vh, size = COMPANION_SIZE) => {
  const b = bounds(vw, vh, size);
  return { x: b.maxX - 16, y: b.maxY };
};

// เก็บตำแหน่งเป็นสัดส่วนของจอ เปลี่ยนขนาดหน้าต่างแล้วยังอยู่ที่เดิมตามสัดส่วน
export function toRatio(pos, vw, vh, size = COMPANION_SIZE) {
  const b = bounds(vw, vh, size);
  const w = b.maxX - b.minX;
  const h = b.maxY - b.minY;
  return { fx: w > 0 ? (pos.x - b.minX) / w : 1, fy: h > 0 ? (pos.y - b.minY) / h : 1 };
}
export function fromRatio(r, vw, vh, size = COMPANION_SIZE) {
  const b = bounds(vw, vh, size);
  return clampPos({ x: b.minX + r.fx * (b.maxX - b.minX), y: b.minY + r.fy * (b.maxY - b.minY) }, vw, vh, size);
}

const KEY = 'nongtrip-companion-pos';
export function loadRatio(storage = globalThis.localStorage) {
  try {
    const raw = JSON.parse(storage?.getItem(KEY) ?? 'null');
    if (raw && Number.isFinite(raw.fx) && Number.isFinite(raw.fy)) return { fx: clamp(raw.fx, 0, 1), fy: clamp(raw.fy, 0, 1) };
  } catch { /* ที่เก็บเป็นของเสริม ใช้ไม่ได้ก็ใช้ตำแหน่งตั้งต้น */ }
  return null;
}
export function saveRatio(ratio, storage = globalThis.localStorage) {
  try { storage?.setItem(KEY, JSON.stringify(ratio)); } catch { /* ไม่เป็นไร */ }
}

// เลือกปลายทางเดินรอบถัดไป: ซ้ายหรือขวา ระยะ 120-360 พิกเซล ชนขอบแล้วกลับด้าน rand คือค่า 0..1
export function pickWalkTarget(x, vw, size = COMPANION_SIZE, rand = Math.random, rand2 = Math.random) {
  const b = bounds(vw, 0, size);
  const dist = 120 + Math.round(rand() * 240);
  let dir = rand2() < 0.5 ? -1 : 1;
  if (x + dir * dist > b.maxX || x + dir * dist < b.minX) {
    const flipped = x - dir * dist;
    if (flipped >= b.minX && flipped <= b.maxX) dir = -dir;
  }
  return clamp(x + dir * dist, b.minX, b.maxX);
}

// เวลาพัก (มิลลิวินาที) ก่อนเดินรอบถัดไป 2.5-7 วินาที
export const nextRestDelay = (rand = Math.random) => 2500 + Math.round(rand() * 4500);
// เวลาก่อนเล่นท่าเล่นเอง (โบกมือ ผิวปาก ขยิบตา) 7-16 วินาที
export const nextActDelay = (rand = Math.random) => 7000 + Math.round(rand() * 9000);

// ก้าวเดินหนึ่งเฟรม: คืนตำแหน่งใหม่และว่าถึงปลายทางหรือยัง dt เป็นวินาที
export function stepToward(x, target, dt, speed = WALK_SPEED) {
  const delta = target - x;
  const move = speed * dt;
  if (Math.abs(delta) <= move) return { x: target, arrived: true, dir: Math.sign(delta) || 1 };
  return { x: x + Math.sign(delta) * move, arrived: false, dir: Math.sign(delta) };
}

// ท่าเล่นเองตอนยืนพัก (mood ท่าโบก หรือสีหน้าของท่า front)
export const IDLE_ACTS = [
  { mood: 'wave', ms: 2200 },
  { expression: 'whistle', ms: 1800 },
  { expression: 'wink-left', ms: 1100 },
  { expression: 'smirk', ms: 1500 },
  { expression: 'tongue', ms: 1200 },
  { expression: 'squint', ms: 1300 },
];
export const pickAct = (rand = Math.random) => IDLE_ACTS[Math.min(IDLE_ACTS.length - 1, Math.floor(rand() * IDLE_ACTS.length))];

// ท่าทาง/อารมณ์จากสถานะ: งานค้นอยู่ → คิด, ตอบเสร็จ → ยิ้ม, ผิดพลาด → ร้องไห้
// พิมพ์อยู่ → ตั้งใจฟัง (ตาโต) ชี้ → ตาเป็นดาว กด → ยิ้มกว้าง ถูกหิ้วลากอยู่ → ตกใจ
export function companionFace({ open, status, typing, hover, pressed, dragging }) {
  if (dragging) return { mood: 'front', expression: 'afraid' };
  if (pressed) return { mood: 'front', expression: 'grin' };
  if (status === 'error') return { mood: 'front', expression: 'crying' };
  if (status === 'searching' || status === 'answering') return { mood: 'think' };
  if (status === 'done') return { mood: 'front', expression: 'grin' };
  if (open && typing) return { mood: 'front', expression: 'star-eyes' };
  if (hover) return { mood: 'front', expression: 'star-eyes' };
  return { mood: 'front' };
}

// ตำแหน่งหน้าต่างแชต: วางเหนือตัวมาสคอตถ้าอยู่ครึ่งล่างของจอ ใต้ตัวถ้าอยู่ครึ่งบน ชิดขอบทางฝั่งที่ตัวอยู่
// จอแคบ (< NARROW) เป็นแผ่นเต็มความกว้างติดล่างจอ
export function panelPlacement(pos, vw, vh, size = COMPANION_SIZE) {
  if (vw < NARROW) {
    const height = Math.min(Math.round(vh * 0.8), 600);
    return { sheet: true, left: 8, top: vh - height - 8, width: vw - 16, height };
  }
  const width = Math.min(390, vw - EDGE * 2);
  const h = bodyHeight(size);
  const gap = 10;
  const below = pos.y + h / 2 < vh / 2;
  const room = below ? vh - (pos.y + h + gap) - EDGE : pos.y - gap - EDGE;
  const height = Math.max(280, Math.min(560, room));
  const cx = pos.x + size / 2;
  const left = clamp(cx < vw / 2 ? pos.x : pos.x + size - width, EDGE, vw - width - EDGE);
  const top = below ? pos.y + h + gap : pos.y - gap - height;
  return { sheet: false, left, top: clamp(top, EDGE, vh - height - EDGE), width, height, below };
}

// คำทักตอนเข้าเว็บครั้งแรกของแต่ละแท็บ
export const GREETING = ['สวัสดี! ถามน้องทริปเรื่องที่เที่ยวได้นะ', 'Hi! Ask NongTrip about places to go.'];
