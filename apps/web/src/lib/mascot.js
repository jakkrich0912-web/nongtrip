// สีหน้าน้องทริปชุด v2 (assets/mascot/expressions-v2) ภาพเต็มทุกภาพขนาด 420x540 ตำแหน่งตัวไม่ขยับ
// สลับทั้งภาพ ไม่ซ้อนหน้า ไม่แก้ภาพ ดู docs/NONGTRIP_MASCOT.md
const FILES = import.meta.glob('../assets/mascot/expressions-v2/*.png', { eager: true, query: '?url', import: 'default' });

export const EXPRESSIONS = Object.fromEntries(
  Object.entries(FILES).map(([path, url]) => [path.split('/').pop().replace(/\.png$/, ''), url]),
);

// ชุดที่ประกาศไว้ใน manifest (front คือภาพฐาน) ใช้ตรวจว่าชื่อที่ขอมีจริง
export const EXPRESSION_NAMES = Object.keys(EXPRESSIONS).filter((n) => n !== 'front');

// ผืนภาพ 420x540 วาง front.webp (373x520) ที่ x=23 y=20 จึงใช้ตัวเลขนี้จัดกรอบให้ขนาดตัวเท่าเดิม
export const CANVAS = { w: 420, h: 540, srcW: 373, srcH: 520, x: 23, y: 20 };

export const expressionUrl = (name) => EXPRESSIONS[name] ?? EXPRESSIONS.front;

// จังหวะกะพริบตา: ครึ่ง → ปิด → ครึ่ง → ตาปกติ (มิลลิวินาทีต่อเฟรม)
export const BLINK_FRAMES = [['blink-half', 70], ['blink-closed', 90], ['blink-half', 70]];

// แตะซ้ำ ๆ: 1-2 ครั้งยิ้มกว้าง 3-4 ครั้งโอ๊ย 5 ครั้งขึ้นไปโกรธ
export function tapExpression(count) {
  if (count >= 5) return 'angry';
  if (count >= 3) return 'ouch';
  return 'grin';
}

// ช่วงเวลา (มิลลิวินาที) ก่อนกะพริบครั้งต่อไป สุ่ม 3-6 วินาที rand คือค่า 0..1
export const nextBlinkDelay = (rand = Math.random()) => 3000 + Math.round(rand * 3000);

const warmed = new Set();
// โหลดภาพล่วงหน้าตอนว่าง ๆ เพื่อไม่ให้สลับแล้วกะพริบขาว
export function preload(names) {
  if (typeof Image === 'undefined') return;
  for (const name of names) {
    const url = EXPRESSIONS[name];
    if (!url || warmed.has(url)) continue;
    warmed.add(url);
    const img = new Image();
    img.src = url;
  }
}

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
