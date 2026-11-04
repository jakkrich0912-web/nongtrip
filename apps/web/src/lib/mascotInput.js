// ตัวติดตามการขยับของผู้ใช้ร่วมกันทั้งหน้า (มาสคอตหลายตัวใช้ตัวเดียว ไม่ต้องผูกฟังเหตุการณ์ซ้ำ)
// ใช้ตัดสินว่า "ผู้ใช้ไม่ขยับมานานแค่ไหน" (ท่าเล่นเอง) ความเร็วเมาส์ (เขย่า) และตำแหน่งเคอร์เซอร์ (มองตาม/เอียงตัว)
// และปุ่มที่ติด data-mascot-cheer (ชี้แล้วตาเป็นหัวใจ ออกแล้วยิ้ม)
import { SHAKE_SPEED } from './mascotPlay.js';

const state = { x: 0, y: 0, lastInput: -1e9, speed: 0, speedAt: 0, cheer: false, moved: false, pointerType: 'mouse' };
const subs = new Set();
let attached = false;

const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

// ความเร็วเมาส์สะสม ลดลงเองตามเวลา (ครึ่งชีวิตสั้น ๆ) ค่าเกิน SHAKE_SPEED นับว่ากำลังเขย่า
export function pointerSpeed(t = now()) {
  return state.speed * Math.exp(-((t - state.speedAt) / 1000) * 6);
}
export const isShaking = (t) => pointerSpeed(t) > SHAKE_SPEED;

function emit(kind, e) { for (const cb of subs) cb(kind, e); }

const handlers = {
  pointermove(e) {
    const t = now();
    const dx = state.moved ? e.clientX - state.x : 0;
    const dy = state.moved ? e.clientY - state.y : 0;
    state.speed = pointerSpeed(t) + Math.hypot(dx, dy) * 0.004;
    state.speedAt = t;
    state.x = e.clientX; state.y = e.clientY; state.moved = true; state.pointerType = e.pointerType;
    state.lastInput = t;
    emit('move', e);
  },
  pointerdown(e) { state.x = e.clientX; state.y = e.clientY; state.moved = true; state.lastInput = now(); emit('input', e); },
  keydown(e) { state.lastInput = now(); emit('input', e); },
  scroll(e) { state.lastInput = now(); emit('scroll', e); },
  wheel(e) { state.lastInput = now(); emit('input', e); },
  touchstart(e) { state.lastInput = now(); emit('input', e); },
  pointerover(e) {
    const el = e.target?.closest?.('[data-mascot-cheer]');
    if (el && !state.cheer) { state.cheer = true; emit('cheer-in', e); }
  },
  pointerout(e) {
    const el = e.target?.closest?.('[data-mascot-cheer]');
    if (el && state.cheer && !(e.relatedTarget && el.contains(e.relatedTarget))) { state.cheer = false; emit('cheer-out', e); }
  },
};

function attach() {
  if (attached || typeof window === 'undefined') return;
  attached = true;
  for (const [name, fn] of Object.entries(handlers)) window.addEventListener(name, fn, { passive: true, capture: name === 'scroll' });
}
function detach() {
  if (!attached) return;
  attached = false;
  for (const [name, fn] of Object.entries(handlers)) window.removeEventListener(name, fn, { capture: name === 'scroll' });
}

// สมัครรับเหตุการณ์ kind: 'move' | 'input' | 'scroll' | 'cheer-in' | 'cheer-out'
export function subscribeInput(cb) {
  subs.add(cb);
  attach();
  return () => { subs.delete(cb); if (!subs.size) detach(); };
}

export const inputState = state;
export const lastInputAt = () => state.lastInput;

// ผู้ใช้ขยับล่าสุดเมื่อไหร่ (ใช้ตอนไม่ได้สมัครรับ เช่นตัวจับเวลาปลุกเอนจิน) ฟังเหตุการณ์แบบเบา ๆ จนกว่าจะมีคนสมัครจริง
export function touchInput(t = now()) { state.lastInput = t; }

// กันมาสคอตหลายตัวเล่นท่าเองพร้อมกัน: ตัวที่ได้ล็อกเล่นได้ทีละตัว
let actOwner = null;
export const takeActLock = (id) => { if (actOwner && actOwner !== id) return false; actOwner = id; return true; };
export const dropActLock = (id) => { if (actOwner === id) actOwner = null; };
