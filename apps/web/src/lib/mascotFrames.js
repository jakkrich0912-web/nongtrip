// ภาพเคลื่อนไหวน้องทริปทีละเฟรม (assets/mascot/motion/<ชุด>/) อ่านค่าจาก manifest.json ของแต่ละชุด
// ทุกเฟรมผืน 360×480 จุดพื้น (anchor) อยู่ที่เดียวกันทุกเฟรม ท่า hop มีเท้าลอยอยู่ในภาพแล้ว ห้ามเลื่อนชดเชย
// เวลาเล่นสลับทั้งภาพแทนมาสคอตนิ่งเดิม (ไม่ซ้อน) จึงต้องวางให้จุดพื้นและความสูงตัวตรงกับภาพนิ่ง front.webp

const MANIFESTS = import.meta.glob('../assets/mascot/motion/*/manifest.json', { eager: true, import: 'default' });
const FILES = import.meta.glob('../assets/mascot/motion/*/[0-9][0-9].webp', { eager: true, import: 'default' });

export function buildMotions(manifests = MANIFESTS, files = FILES) {
  const out = {};
  for (const [path, m] of Object.entries(manifests)) {
    const dir = path.slice(0, path.lastIndexOf('/') + 1);
    const frames = (m.frames ?? []).map((f) => files[dir + f.file]).filter(Boolean);
    if (!m.name || frames.length !== m.frame_count) continue;      // เฟรมไม่ครบ ไม่ใช้ชุดนี้เลย
    out[m.name] = {
      fps: m.fps, canvas: m.canvas_size, anchor: m.anchor, frames,
      lift: (m.frames ?? []).map((f) => f.ground_clearance_px ?? 0),
    };
  }
  return out;
}

export const MOTIONS = buildMotions();

// ภาพนิ่ง front.webp (373×520): กรอบตัวแมว x 13-360, y 35-484 (วัดจาก alpha) ความสูงตัวในภาพเคลื่อนไหวท่ายืนราว 389 px
export const STILL = { source: [373, 520], cx: 186.5, bottom: 484, height: 449 };
export const MOTION_BODY = 389;

// กล่องของภาพเคลื่อนไหว (px) ภายในกล่องมาสคอตนิ่งกว้าง size: ความสูงตัวเท่าภาพนิ่ง และจุดพื้นตรงกับปลายเท้าภาพนิ่ง
// originX/originY = จุดพื้นในกล่อง ใช้เป็นจุดหมุนตอนสะท้อนซ้าย-ขวา จุดพื้นจึงอยู่ที่เดิม
export function spriteBox(size, motion) {
  const [cw, ch] = motion.canvas;
  const [ax, ay] = motion.anchor;
  const s = size / STILL.source[0];
  const m = (STILL.height * s) / MOTION_BODY;
  const r = (n) => Math.round(n * 100) / 100;
  return {
    width: r(cw * m), height: r(ch * m),
    left: r(STILL.cx * s - ax * m), top: r(STILL.bottom * s - ay * m),
    originX: r(ax * m), originY: r(ay * m), scale: m,
  };
}

// เฟรมที่ควรแสดงเมื่อเล่นไปแล้ว elapsed ms: loops = จำนวนรอบ (Infinity = วนไม่จบ) เล่นครบแล้วคืน -1
export function frameIndex(elapsed, fps, count, loops = Infinity) {
  if (!count || !fps) return -1;
  const n = Math.floor(Math.max(0, elapsed) * fps / 1000);
  if (n >= count * loops) return -1;
  return n % count;
}

// ระยะที่ตัวเคลื่อนไปต่อหนึ่งรอบท่าเดิน (หน่วยพิกเซลของภาพ) วัดจากระยะก้าวของเท้าในภาพ walk
export const WALK_CYCLE_PX = 260;

// fps ของท่าเดินให้เท้าไปกับพื้นพอดีตามความเร็วจริงบนจอ (ไม่ให้ตัวไหลหรือเท้าย่ำอยู่กับที่) จำกัด 5-14 fps
export function walkFps(speedPxPerSec, size, motion = MOTIONS.walk) {
  if (!motion) return 0;
  const { scale } = spriteBox(size, motion);
  const cycles = speedPxPerSec / (WALK_CYCLE_PX * scale);
  return Math.min(14, Math.max(5, cycles * motion.frames.length));
}

// โหลดและถอดรหัสทุกเฟรมของชุดก่อนเล่น (กันภาพว่าง/กะพริบ) โหลดแล้วจำไว้ คืน true เมื่อพร้อม
const ready = new Map();
export function loadMotion(name) {
  const motion = MOTIONS[name];
  if (!motion || typeof Image === 'undefined') return Promise.resolve(false);
  if (!ready.has(name)) {
    ready.set(name, Promise.all(motion.frames.map((src) => new Promise((resolve) => {
      const img = new Image();
      img.onload = () => (img.decode ? img.decode().catch(() => {}) : Promise.resolve()).then(() => resolve(true));
      img.onerror = () => resolve(false);
      img.src = src;
    }))).then((all) => all.every(Boolean)));
  }
  return ready.get(name);
}
