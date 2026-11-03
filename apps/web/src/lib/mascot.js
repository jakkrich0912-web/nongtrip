// สีหน้าน้องทริปชุด v2 (assets/mascot/expressions-v2) ภาพเต็มทุกภาพขนาด 420x540 ตำแหน่งตัวไม่ขยับ
// สลับทั้งภาพ ไม่ซ้อนหน้า ไม่แก้ภาพ ดู docs/NONGTRIP_MASCOT.md
const FILES = import.meta.glob('../assets/mascot/expressions-v2/*.png', { eager: true, query: '?url', import: 'default' });
// ท่าอื่น (wave think happy) แยกโฟลเดอร์ละท่า: expressions-v2/<ท่า>/<สีหน้า>.png
const POSE_FILES = import.meta.glob('../assets/mascot/expressions-v2/*/*.png', { eager: true, query: '?url', import: 'default' });

export const EXPRESSIONS = Object.fromEntries(
  Object.entries(FILES).map(([path, url]) => [path.split('/').pop().replace(/\.png$/, ''), url]),
);

// ชุดที่ประกาศไว้ใน manifest (front คือภาพฐาน) ใช้ตรวจว่าชื่อที่ขอมีจริง
export const EXPRESSION_NAMES = Object.keys(EXPRESSIONS).filter((n) => n !== 'front');

// ผืนภาพ 420x540 วาง front.webp (373x520) ที่ x=23 y=20 จึงใช้ตัวเลขนี้จัดกรอบให้ขนาดตัวเท่าเดิม
export const CANVAS = { w: 420, h: 540, srcW: 373, srcH: 520, x: 23, y: 20 };

export const expressionUrl = (name) => EXPRESSIONS[name] ?? EXPRESSIONS.front;

const POSE_IMAGES = {};
for (const [path, url] of Object.entries(POSE_FILES)) {
  const hit = path.match(/expressions-v2\/([^/]+)\/([^/]+)\.png$/);
  if (hit) (POSE_IMAGES[hit[1]] ??= {})[hit[2]] = url;
}

// ขนาดผืน/ภาพต้นฉบับ/ตำแหน่งวางต้นฉบับบนผืน ต้องตรงกับ manifest.json ของแต่ละท่า (มีเทสต์เทียบ)
// ภาพต้นฉบับ .webp วางบนผืนใหม่โดยไม่ย่อขยาย จึงใช้กรอบอัตราส่วนของต้นฉบับ แล้วดันภาพเต็มให้ล้นกรอบเท่าที่ offset กำหนด
// blink: กะพริบเองตามจังหวะ  tap: สีหน้าตอนแตะ (count คือจำนวนครั้งที่แตะติดกัน)
export const POSE_SETS = {
  front: {
    canvas: [420, 540], source: [373, 520], offset: [23, 20], blink: true, yawn: true, hover: 'star-eyes',
    images: { ...EXPRESSIONS, base: EXPRESSIONS.front }, tap: (count) => tapExpression(count),
  },
  wave: {
    canvas: [420, 537], source: [400, 517], offset: [10, 20], blink: true,
    images: POSE_IMAGES.wave ?? {}, tap: () => 'grin',
  },
  think: {
    canvas: [420, 519], source: [400, 499], offset: [10, 20], blink: true,
    images: POSE_IMAGES.think ?? {}, tap: () => 'grin',
  },
  // happy ตาหยียิ้มอยู่แล้ว ไม่กะพริบเอง: แตะแล้วลืมตามองครู่หนึ่งเป็นปฏิกิริยา
  happy: {
    canvas: [417, 537], source: [397, 517], offset: [10, 20], blink: false,
    images: POSE_IMAGES.happy ?? {}, tap: () => 'blink-half',
  },
};

export const poseUrl = (pose, name) => {
  const set = POSE_SETS[pose];
  return set?.images[name] ?? set?.images.base;
};

const pct = (n) => `${Math.round(n * 10000) / 10000}%`;
// กรอบของท่า (อัตราส่วน = ต้นฉบับ) และตำแหน่ง/ความกว้างของภาพเต็มในกรอบ ตัวมาสคอตจึงอยู่ที่เดิมทุกเฟรม
export function poseFrame(pose) {
  const { canvas, source, offset } = POSE_SETS[pose];
  return {
    frame: { aspectRatio: `${source[0]} / ${source[1]}` },
    image: { left: pct((-offset[0] / source[0]) * 100), top: pct((-offset[1] / source[1]) * 100), width: pct((canvas[0] / source[0]) * 100) },
  };
}

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
// โหลดภาพล่วงหน้าตอนว่าง ๆ เพื่อไม่ให้สลับแล้วกะพริบขาว (pose เริ่มต้นคือ front)
export function preload(names, pose = 'front') {
  if (typeof Image === 'undefined') return;
  for (const name of names) {
    const url = POSE_SETS[pose]?.images[name];
    if (!url || warmed.has(url)) continue;
    warmed.add(url);
    const img = new Image();
    img.src = url;
  }
}

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
