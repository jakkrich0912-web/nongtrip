// พฤติกรรมของมาสคอตเวลาเล่นด้วย: ชี้/แตะ/ดึง/เขย่า และท่าเล่นเองตอนผู้ใช้ไม่ขยับ
// ไฟล์นี้เป็นตรรกะล้วน (ไม่แตะ DOM) ตัดสินแค่ว่า "ตอนนี้ควรเป็นสีหน้าไหน" แล้วให้ MascotSheet วาด
// สีหน้าทุกแบบเป็นภาพทั้งภาพจากชุด expressions-v2 ไม่มีการเอาชิ้นส่วนมาซ้อนทับ จึงไม่มีตาซ้อน/ขอบดำ
//
// กติกา: ระหว่างที่ผู้ใช้ขยับอยู่ มาสคอตไม่เปลี่ยนสีหน้าเอง ท่าเล่นเองเริ่มได้หลังไม่มีการขยับ 30-45 วินาที
// และการขยับครั้งแรกหลังจากนั้นหยุดท่าทันที

// ภาพเต็มของท่า front คือผืน 420x540 (ภาพนี้คือกรอบ uv 0..1 ของแผ่น)
export const FRONT_CANVAS = [420, 540];

const ell = (px, py, cx, cy, rx, ry = rx) => ((px - cx) / rx) ** 2 + ((py - cy) / ry) ** 2 <= 1;

// ชิ้นส่วนที่ชี้/แตะ ใช้พิกัดพิกเซลบนผืน 420x540 ของท่า front (ดูจาก front.png)
export function zoneAt(u, v) {
  const px = u * FRONT_CANVAS[0];
  const py = v * FRONT_CANVAS[1];
  if (ell(px, py, 308, 62, 30, 34)) return 'pin';
  if (py < 190) return 'hat';
  if (py < 320) {
    if (ell(px, py, 158, 228, 40, 42)) return 'eyeL';
    if (ell(px, py, 300, 238, 40, 42)) return 'eyeR';
    if (ell(px, py, 232, 237, 22, 18)) return 'nose';
    if (ell(px, py, 228, 272, 40, 28)) return 'mouth';
    if (ell(px, py, 118, 264, 32, 30) || ell(px, py, 332, 276, 32, 30)) return 'cheek';
    return 'face';
  }
  if (py < 425) return 'camera';
  if (py < 495) return 'belly';
  return 'feet';
}
// eyeL/eyeR คือตาซ้าย/ขวาบนหน้าจอ ภาพ wink-right หลับตาซ้ายจอ ภาพ wink-left หลับตาขวาจอ

// ชี้ค้างเกิน 80 มิลลิวินาทีถึงจะตอบ ชิ้นส่วนที่ไม่อยู่ในรายการ (หมวก แก้ม หน้า ตัว) ไม่เปลี่ยนสีหน้า
export const HOVER_FACE = { eyeL: 'wink-right', eyeR: 'wink-left', nose: 'cross-eyed', mouth: 'kiss' };
export const HOVER_DELAY_MS = 80;

// แตะ: 'act:ชื่อ' คือเล่นท่าต่อเนื่อง นอกนั้นคือสีหน้าที่ค้างสั้น ๆ
export const TAP_FACE = {
  hat: 'angry', pin: 'star-eyes', eyeL: 'ouch', eyeR: 'ouch', nose: 'act:sneeze', mouth: 'tongue',
  cheek: 'shy', face: 'grin', camera: 'smirk', belly: 'squint', feet: 'afraid',
};
export const TAP_HOLD_MS = 1100;

// ระหว่างกดค้างและดึง: ดึงยิ่งไกลยิ่งตกใจ (ระยะเป็นหน่วย uv ของแผ่น)
export function pressFace(pull) {
  if (pull > 0.24) return 'afraid';
  if (pull > 0.02) return 'ouch';
  return null;
}
export const PULL_WINDOW_MS = 14000;
// ปล่อยมือ: ดึงน้อยทำหน้ามุ่ย ดึงไกลมึน ดึงรัว ๆ โกรธแล้วร้องไห้ n คือจำนวนครั้งที่ดึงใน 14 วินาทีรวมครั้งนี้
export function releaseFace(pull, n) {
  if (n >= 8) return { face: 'crying', ms: 2600 };
  if (n >= 5) return { face: 'angry', ms: 2600 };
  if (pull > 0.22) return { face: 'dizzy', ms: 700 + pull * 2800 };
  if (pull > 0.1) return { face: 'squint', ms: 700 + pull * 2800 };
  return { face: 'blink-half', ms: 700 + pull * 2800 };
}
// ดึงสั้นเกินและกดไม่นาน ถือเป็นการแตะ
export const isTap = (pull, heldMs) => pull < 0.03 && heldMs < 380;

// เขย่าเมาส์เร็ว ๆ ทำให้ปั่นป่วน เขย่าต่อเนื่องจนเวียนหัว shake คือ 0..1 (ดู MascotSheet)
export function shakeFace(shake) {
  if (shake > 0.92) return 'dizzy';
  if (shake > 0.55) return 'squint';
  return null;
}
export const SHAKE_SPEED = 1.5; // ความเร็วสะสมที่นับว่าเขย่า

// แตะรัว ๆ ที่มาสคอตตัวเดิมภายใน 1.5 วินาที: ครั้งที่ 5 ขึ้นไปโกรธ
export function tapEscalation(count, zoneFace) {
  return count >= 5 ? 'angry' : zoneFace;
}

// ---- ท่าเล่นเอง ----
// ทุกขั้น: face ชื่อภาพ, fade มิลลิวินาทีของการเฟด (ไม่เกิน 70 ตอนวาด), hold เวลาค้าง
// jolt [u,v,dx,dy,r] ผลักผิว, lean [x,y] เอียงตัว, fly/hand [u,v,ms] ย้ายของประกอบฉาก, grip 'on'|'off' มือจับ/ปล่อยแก้ม
export const SPOT = { nose: [0.552, 0.44], cheekR: [0.79, 0.51], cheekL: [0.28, 0.485] };

export const ACTS = {
  yawn: [
    { face: 'blink-half', fade: 140, hold: 240 }, { face: 'yawn', fade: 170, hold: 1100 },
    { face: 'blink-half', fade: 150, hold: 200 }, { face: 'neutral', fade: 150, hold: 200 },
  ],
  whistle: [
    { face: 'whistle', fade: 150, hold: 700 }, { face: 'neutral', fade: 100, hold: 260 },
    { face: 'whistle', fade: 100, hold: 700 }, { face: 'neutral', fade: 100, hold: 200 },
  ],
  sneeze: [
    { face: 'pre-sneeze', fade: 130, hold: 380 }, { face: 'blink-half', fade: 90, hold: 120 },
    { face: 'pre-sneeze', fade: 90, hold: 560 },
    { face: 'sneeze', fade: 50, hold: 300, jolt: [0.55, 0.6, 0, 1.5, 0.34], lean: [0, 0.03] },
    { face: 'dizzy', fade: 110, hold: 620 }, { face: 'shy', fade: 140, hold: 650 },
  ],
  flirt: [
    { face: 'smirk', fade: 130, hold: 520 }, { face: 'wink-right', fade: 80, hold: 420 },
    { face: 'kiss', fade: 120, hold: 560 }, { face: 'heart-eyes', fade: 120, hold: 900 },
    { face: 'shy', fade: 160, hold: 620 },
  ],
  cheeky: [
    { face: 'wink-left', fade: 90, hold: 340 }, { face: 'tongue', fade: 110, hold: 900 },
    { face: 'grin', fade: 120, hold: 620 },
  ],
  cross: [
    { face: 'cross-eyed', fade: 140, hold: 900 }, { face: 'tongue', fade: 110, hold: 700 },
    { face: 'grin', fade: 90, hold: 800 },
  ],
  wow: [{ face: 'star-eyes', fade: 130, hold: 1000 }, { face: 'grin', fade: 140, hold: 640 }],
  sad: [
    { face: 'afraid', fade: 140, hold: 500 }, { face: 'crying', fade: 240, hold: 1500 },
    { face: 'shy', fade: 200, hold: 520 },
  ],
  // งีบหลับ: ตาค่อยปิด เอียงหัว ถ้าผู้ใช้ขยับระหว่างหลับ (wake) จะสะดุ้งตื่นแทนการหยุดเฉย ๆ
  doze: [
    { face: 'blink-half', fade: 450, hold: 700, lean: [0.006, 0.006] },
    { face: 'blink-closed', fade: 320, hold: 500, lean: [0.012, 0.012] },
    { face: 'blink-half', fade: 200, hold: 340 },
    { face: 'blink-closed', fade: 400, hold: 1100, lean: [0.02, 0.02] },
    { face: 'blink-closed', fade: 260, hold: 3400, lean: [0.03, 0.03], wake: true },
    { face: 'ouch', fade: 50, hold: 650, jolt: [0.55, 0.5, 0, -0.9, 0.3] },
  ],
  // แมลงวันบินมาเกาะจมูก แล้วถูกเป่าให้บินไป
  fly: [
    { face: 'base', fade: 40, hold: 620, fly: [0.92, 0.2, 560] }, { face: 'base', fade: 40, hold: 680, fly: [0.1, 0.32, 610] },
    { face: 'base', fade: 40, hold: 640, fly: [0.9, 0.66, 580] }, { face: 'base', fade: 40, hold: 600, fly: [0.16, 0.62, 540] },
    { face: 'base', fade: 40, hold: 520, fly: [...SPOT.nose, 470] },
    { face: 'cross-eyed', fade: 110, hold: 950, jolt: [0.55, 0.44, 0, 0.28, 0.05] },
    { face: 'whistle', fade: 90, hold: 340, fly: [0.55, 0.3, 250] }, { face: 'neutral', fade: 110, hold: 480, fly: [...SPOT.nose, 290] },
    { face: 'cross-eyed', fade: 90, hold: 560, jolt: [0.55, 0.44, 0, 0.28, 0.05] },
    { face: 'whistle', fade: 90, hold: 620, fly: [1.5, -0.35, 540] }, { face: 'smirk', fade: 120, hold: 600 },
  ],
  // มือผีมาดึงแก้มแล้วปล่อยให้เด้งกลับ
  tug: [
    { face: 'neutral', fade: 90, hold: 760, hand: [...SPOT.cheekR, 610] },
    { face: 'ouch', fade: 90, hold: 240, grip: 'on' },
    { face: 'afraid', fade: 90, hold: 620, hand: [0.95, 0.5, 500] }, { face: 'afraid', fade: 90, hold: 240, hand: [0.86, 0.56, 190] },
    { face: 'afraid', fade: 90, hold: 240, hand: [0.98, 0.48, 190] }, { face: 'afraid', fade: 90, hold: 260, hand: [0.9, 0.52, 200] },
    { face: 'dizzy', fade: 90, hold: 1000, hand: [1.4, 0.22, 800], grip: 'off' }, { face: 'angry', fade: 120, hold: 620 },
  ],
};
export const ROTATION = ['yawn', 'fly', 'flirt', 'sneeze', 'tug', 'cross', 'whistle', 'doze', 'cheeky', 'wow', 'sad'];

export const IDLE_MIN_MS = 30000;
export const IDLE_SPAN_MS = 15000;
export const nextIdleDelay = (rand = Math.random()) => IDLE_MIN_MS + rand * IDLE_SPAN_MS;

// ถึงเวลาเล่นท่าเองหรือยัง: ต้องไม่มีใครขยับมา nextIdle มิลลิวินาที และผู้ใช้ไม่ได้ตั้งลดการเคลื่อนไหว
export function idleDue({ now, lastInput, start, nextIdle, reduced, pressed, acting }) {
  if (reduced || pressed || acting) return false;
  return now - Math.max(lastInput, start) > nextIdle;
}

// หยิบท่าถัดไปจากคิวหมุนเวียน (คิวหมดแล้วเติมใหม่ครบชุด)
export function takeAct(queue) {
  if (!queue.length) queue.push(...ROTATION);
  return queue.shift();
}

// ---- สายตามองตามเคอร์เซอร์ (ต้องมีภาพ gaze-* 16 ทิศ ถ้ายังไม่มีก็ข้ามไปเฉย ๆ) ----
export const GAZE_RING = ['e', 'ene', 'ne', 'nne', 'n', 'nnw', 'nw', 'wnw', 'w', 'wsw', 'sw', 'ssw', 's', 'sse', 'se', 'ese'];
export const GAZE_NAMES = GAZE_RING.map((d) => `gaze-${d}`);
export const hasGaze = (images) => GAZE_NAMES.every((n) => images?.[n]);
// dx,dy คือเวกเตอร์จากกึ่งกลางหน้าไปเคอร์เซอร์ (y ชี้ลง) ใกล้เกินไปคืน null = ตามองตรง
export function gazeFor(dx, dy, dead = 0.13) {
  if (Math.hypot(dx, dy) < dead) return null;
  const a = (Math.atan2(-dy, dx) + Math.PI * 2) % (Math.PI * 2);
  return `gaze-${GAZE_RING[Math.round(a / (Math.PI / 8)) % 16]}`;
}

// ท่าอื่น (wave think happy) มีภาพน้อยกว่า front: ชื่อที่ไม่มีให้ใช้ภาพที่ใกล้ที่สุด แล้วค่อยกลับไปภาพฐาน
const NEGATIVE = new Set(['ouch', 'afraid', 'angry', 'crying', 'dizzy', 'squint', 'pre-sneeze', 'sneeze']);
export function resolveFace(images, name) {
  if (name === 'base' || name == null) return 'base';
  if (images[name]) return name;
  if (NEGATIVE.has(name) && images['blink-half']) return 'blink-half';
  if (!NEGATIVE.has(name) && images.grin) return 'grin';
  return 'base';
}

// ชื่อสีหน้าทั้งหมดที่ตรรกะนี้อาจขอ ใช้ตรวจว่ามีภาพรองรับครบ
export function allFaceNames() {
  const names = new Set([...Object.values(HOVER_FACE), ...Object.values(TAP_FACE).filter((n) => !n.startsWith('act:'))]);
  for (const steps of Object.values(ACTS)) for (const s of steps) names.add(s.face);
  for (const n of ['afraid', 'ouch', 'dizzy', 'squint', 'blink-half', 'angry', 'crying', 'heart-eyes', 'grin']) names.add(n);
  names.delete('base');
  return [...names];
}
