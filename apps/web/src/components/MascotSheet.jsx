import { useEffect, useRef } from 'react';
import { createSheet, OVER } from '../lib/mascotSheet.js';
import { createRenderer } from '../lib/mascotGl.js';
import {
  ACTS, HOVER_DELAY_MS, HOVER_FACE, PULL_WINDOW_MS, SHAKE_SPEED, TAP_FACE, TAP_HOLD_MS, gazeFor, hasGaze, idleDue,
  isTap, nextIdleDelay, pressFace, releaseFace, resolveFace, shakeFace, takeAct, tapEscalation, zoneAt,
} from '../lib/mascotPlay.js';
import { BLINK_FRAMES, POSE_SETS, nextBlinkDelay } from '../lib/mascot.js';
import {
  dropActLock, inputState, lastInputAt, pointerSpeed, subscribeInput, takeActLock, touchInput,
} from '../lib/mascotInput.js';

// ตัวเล่นของมาสคอต: วาดบน canvas ด้วยแผ่นผิวยืดได้ และตัดสินสีหน้าจากการชี้/แตะ/ดึง/เขย่า/ท่าเล่นเอง
// ตรรกะอยู่ใน lib/mascotPlay.js ฟิสิกส์อยู่ใน lib/mascotSheet.js ไฟล์นี้ต่อทั้งหมดเข้ากับ DOM
// ลำดับการโหลดภาพ: ภาพฐานก่อน (กะพริบ/แตะใช้ทันที) แล้วที่เหลือทยอยโหลดเบื้องหลัง
const FRONT_ORDER = ['blink-half', 'blink-closed', 'grin', 'wink-left', 'wink-right', 'cross-eyed', 'kiss', 'ouch', 'afraid', 'angry', 'tongue', 'smirk', 'squint', 'shy', 'dizzy', 'star-eyes', 'heart-eyes', 'pre-sneeze', 'sneeze', 'yawn', 'whistle', 'crying', 'neutral'];
const LEAN_SCALE = 0.5;
const ENERGY_REST = 0.4; // พลังงานต่ำกว่านี้ถือว่านิ่ง หยุดคำนวณ/วาด
let uid = 0;

export default function MascotSheet({ pose, size, imageStyle, forcedFace, idleActs, mountedAt, reduced, hostRef, apiRef, onReady, onFail, onTap }) {
  const canvasRef = useRef(null);
  const flyRef = useRef(null);
  const handRef = useRef(null);
  const live = useRef({});
  live.current = { forcedFace, onTap, reduced };
  const set = POSE_SETS[pose];

  useEffect(() => {
    const host = hostRef.current;
    const canvas = canvasRef.current;
    if (!host || !canvas) return undefined;
    const images = set.images;
    const id = ++uid;
    const sheet = createSheet({ n: size >= 200 ? 64 : size >= 110 ? 48 : 36 });
    let renderer;
    try { renderer = createRenderer(canvas, sheet); } catch { renderer = null; }
    if (!renderer) { onFail?.(); return undefined; }
    const r = renderer;
    const zoneOf = pose === 'front' ? zoneAt : () => 'face';

    let alive = true;
    let ready = false;
    let visible = true;
    let alpha = null;
    let rafId = 0;
    let timerId = 0;
    let last = performance.now();
    let dirty = true;

    // ---- โหลดภาพ ----
    const pending = new Set();
    const queue = [];
    let inflight = 0;
    const pump = () => {
      while (alive && inflight < 3 && queue.length) {
        const name = queue.shift();
        inflight++;
        const img = new Image();
        img.onload = () => {
          inflight--;
          if (alive) { r.upload(name, img); if (name === 'base') init(img); dirty = true; kick(); }
          pump();
        };
        img.onerror = () => { inflight--; pending.delete(name); pump(); };
        img.src = images[name];
      }
    };
    const want = (name, first = false) => {
      if (!images[name] || r.has(name) || pending.has(name)) return;
      pending.add(name);
      if (first) queue.unshift(name); else queue.push(name);
      pump();
    };

    // ---- สถานะ ----
    let faceA = 'base'; let faceB = 'base'; let fadeT = 0; let fadeMs = 1;
    let pressed = false; let downAt = 0; let downU = 0; let downV = 0;
    let pu = 0.5; let pv = 0.5; let onHead = false; let zone = null; let zoneSince = 0; let lastPx = 0; let lastPy = 0;
    let moodFace = null; let moodUntil = 0; let cheered = false;
    let taps = { n: 0, at: 0 }; let pulls = [];
    let physAwake = false; let shake = 0;
    let act = null; let actI = 0; let actT = 0; let rotation = []; let nextIdle = nextIdleDelay();
    let wantLean = [0, 0]; let leanX = 0; let leanY = 0; let lvX = 0; let lvY = 0;
    let blinkI = -1; let blinkUntil = 0; let nextBlink = performance.now() + nextBlinkDelay();
    let handHeld = false; let moveT = 0; let moveMs = 1;
    let handFrom = [1.4, 0.9]; let handTo = [1.4, 0.9]; let flyFrom = [1.4, 0]; let flyTo = [1.4, 0];
    let handPos = [1.4, 0.9]; let flyPos = [1.4, 0];
    const gazeOn = pose === 'front' && hasGaze(images);

    const toUv = (x, y) => {
      const b = canvas.getBoundingClientRect();
      return [((x - b.left) / b.width - 0.5) * OVER + 0.5, ((y - b.top) / b.height - 0.5) * OVER + 0.5];
    };
    const solid = (u, v) => alpha && u >= 0 && v >= 0 && u < 1 && v < 1 && alpha[(((v * 128) | 0) * 128 + ((u * 128) | 0)) * 4 + 3] > 40;
    const place = (el, u, v) => { if (el) { el.style.left = `${u * 100}%`; el.style.top = `${v * 100}%`; } };

    function kick() {
      if (!alive || rafId) return;
      clearTimeout(timerId); timerId = 0;
      rafId = requestAnimationFrame(tick);
    }

    // ---- ท่าเล่นเอง ----
    function endAct() {
      if (act) dropActLock(id);
      act = null; wantLean = [0, 0];
      if (handHeld) { handHeld = false; sheet.releaseHold(); }
      if (flyRef.current) flyRef.current.style.opacity = 0;
      if (handRef.current) { handRef.current.style.opacity = 0; handRef.current.classList.remove('shut'); }
    }
    function advanceAct(now) {
      actI++;
      if (!act || actI >= act.length) { endAct(); return; }
      const s = act[actI];
      actT = now; wantLean = s.lean ?? [0, 0];
      if (s.jolt) { sheet.poke(...s.jolt); physAwake = true; }
      if (s.fly) { flyFrom = flyPos; flyTo = [s.fly[0], s.fly[1]]; moveT = now; moveMs = s.fly[2]; }
      if (s.hand) { handFrom = handPos; handTo = [s.hand[0], s.hand[1]]; moveT = now; moveMs = s.hand[2]; }
      if (s.grip === 'on') {
        sheet.takeHold(handPos[0], handPos[1], 0.22); handHeld = true; physAwake = true;
        handRef.current?.classList.add('shut');
      } else if (s.grip === 'off' && handHeld) {
        handHeld = false; sheet.releaseHold(); handRef.current?.classList.remove('shut');
      }
    }
    function startAct(name, now) {
      const steps = ACTS[name];
      if (!steps || pose !== 'front') return false;
      if (act) endAct();
      act = steps; actI = -1; actT = now;
      if (act === ACTS.fly) { flyPos = [1.35, 0.02]; flyFrom = flyPos; flyTo = flyPos; if (flyRef.current) flyRef.current.style.opacity = 1; }
      if (act === ACTS.tug) { handPos = [1.3, 0.86]; handFrom = handPos; handTo = handPos; if (handRef.current) { handRef.current.style.opacity = 1; handRef.current.classList.remove('shut'); } }
      for (const s of act) want(s.face === 'base' ? 'base' : s.face, true);
      advanceAct(now);
      return true;
    }
    // ผู้ใช้ขยับระหว่างท่าเล่นเอง: หยุดทันที (งีบอยู่จะสะดุ้งตื่นก่อน)
    function userInput(now) {
      nextIdle = nextIdleDelay();
      if (!act) return;
      if (act === ACTS.doze && actI < act.length - 1) { actI = act.length - 2; advanceAct(now); } else if (act !== ACTS.doze) endAct();
    }

    // ---- แตะ / ดึง ----
    function tap(z, now, u, v) {
      taps = { n: now - taps.at < 1500 ? taps.n + 1 : 1, at: now };
      if (pose === 'front') {
        const reaction = tapEscalation(taps.n, TAP_FACE[z] ?? 'grin');
        if (reaction.startsWith('act:')) startAct(reaction.slice(4), now);
        else { moodFace = reaction; moodUntil = now + TAP_HOLD_MS; }
      } else { moodFace = set.tap(taps.n); moodUntil = now + TAP_HOLD_MS; }
      want(moodFace ?? 'grin', true);
      sheet.poke(u, v, 0, 0.5, 0.06); physAwake = true;
      live.current.onTap?.();
      kick();
    }
    function release() {
      if (!pressed) return;
      const now = performance.now();
      const L = sheet.pull(); const z = zoneOf(downU, downV); const held = now - downAt;
      pressed = false; sheet.releaseHold(); host.style.cursor = '';
      pulls = pulls.filter((t) => now - t < PULL_WINDOW_MS);
      if (isTap(L, held)) { tap(z, now, downU, downV); return; }
      pulls.push(now);
      const res = releaseFace(L, pulls.length);
      moodFace = pose === 'front' ? res.face : 'blink-half'; moodUntil = now + res.ms;
      want(moodFace, true);
      kick();
    }

    const onDown = (e) => {
      const now = performance.now();
      const [u, v] = toUv(e.clientX, e.clientY);
      if (!ready || !solid(u, v)) return;
      userInput(now);
      if (act) endAct();
      pressed = true; downAt = now; downU = u; downV = v; moodFace = null;
      sheet.takeHold(u, v); physAwake = true;
      try { host.setPointerCapture(e.pointerId); } catch { /* บางเบราว์เซอร์ไม่รองรับ ไม่เป็นไร */ }
      host.style.cursor = 'grabbing';
      for (const n of ['ouch', 'afraid']) want(n, true);
      kick();
    };
    const onMove = (e) => {
      if (!ready) return;
      const [u, v] = toUv(e.clientX, e.clientY);
      const dx = e.clientX - lastPx; const dy = e.clientY - lastPy; lastPx = e.clientX; lastPy = e.clientY;
      pu = u; pv = v;
      onHead = Boolean(solid(u, v));
      const z = onHead && e.pointerType !== 'touch' ? zoneOf(u, v) : null;
      if (z !== zone) { zone = z; zoneSince = performance.now(); if (z && HOVER_FACE[z]) want(HOVER_FACE[z], true); }
      if (!pressed) host.style.cursor = onHead ? 'grab' : '';
      if (pressed) {
        sheet.dragTo(u, v);
        // ดึงไกลแล้วค่อยโหลดสีหน้าที่ใช้ตอนดึง
      } else if (onHead) { sheet.poke(u, v, dx * 0.00035, dy * 0.00035, 0.07); physAwake = true; }
      kick();
    };
    const onLeave = () => { zone = null; onHead = false; if (!pressed) host.style.cursor = ''; kick(); };
    const onKeyTap = () => { if (ready) tap('face', performance.now(), 0.5, 0.5); };
    if (apiRef) apiRef.current = { tapKey: onKeyTap };

    host.addEventListener('pointerdown', onDown);
    host.addEventListener('pointermove', onMove);
    host.addEventListener('pointerleave', onLeave);
    window.addEventListener('pointerup', release);
    window.addEventListener('pointercancel', release);
    const unsubscribe = subscribeInput((kind) => {
      const now = performance.now();
      if (kind === 'cheer-in') { cheered = true; want('heart-eyes', true); moodFace = 'heart-eyes'; moodUntil = now + 1e7; kick(); return; }
      if (kind === 'cheer-out') { if (cheered) { cheered = false; moodFace = 'grin'; moodUntil = now + 700; kick(); } return; }
      if (kind === 'move' || kind === 'input' || kind === 'scroll') {
        userInput(now);
        if (kind === 'move' && visible) kick();
        if (kind === 'move' && !pressed) {
          const [u, v] = toUv(inputState.x, inputState.y);
          pu = Math.max(-1.2, Math.min(2.2, u)); pv = Math.max(-1.2, Math.min(2.2, v));
        }
        if (kind === 'move' && pointerSpeed(now) > SHAKE_SPEED) kick();
      }
    });
    const io = new IntersectionObserver((es) => { visible = es[0].isIntersecting; if (visible) { dirty = true; kick(); } }, { threshold: 0 });
    io.observe(host);
    const ro = new ResizeObserver(() => { const b = canvas.getBoundingClientRect(); if (b.width) { r.resize(b.width, b.height); dirty = true; kick(); } });
    ro.observe(canvas);
    const onLost = (e) => { e.preventDefault(); alive = false; onFail?.(); };
    canvas.addEventListener('webglcontextlost', onLost);

    // ---- สีหน้า ----
    const show = (name, ms, now) => {
      const key = resolveFace(images, name);
      if (!r.has(key)) { want(key, true); return; }
      if (key === faceB) return;
      faceA = (now - fadeT) / fadeMs > 0.5 ? faceB : faceA;
      faceB = key; fadeT = now; fadeMs = Math.min(70, Math.max(1, ms));
      dirty = true;
    };

    // ---- เฟรม ----
    function tick(now) {
      rafId = 0;
      if (!alive) return;
      const dt = Math.min(0.04, (now - last) / 1000); last = now;
      const f = (k) => 1 - Math.exp(-dt * k);

      if (visible && ready) {
        const speed = pointerSpeed(now);
        shake += ((speed > SHAKE_SPEED ? 1 : 0) - shake) * f(speed > SHAKE_SPEED ? 1.2 : 0.9);
        const { forcedFace: forced, reduced: calm } = live.current;

        if (act && now - actT > act[actI].hold) advanceAct(now);
        else if (!act && !forced && idleActs && !document.hidden
          && idleDue({ now, lastInput: lastInputAt(), start: mountedAt, nextIdle, reduced: calm, pressed, acting: false })
          && takeActLock(id)) {
          if (!startAct(takeAct(rotation), now)) dropActLock(id);
          touchInput(now); nextIdle = nextIdleDelay();
        }

        // ของประกอบฉาก (แมลงวัน มือผี)
        const mk = Math.min(1, (now - moveT) / moveMs); const me = mk * mk * (3 - 2 * mk);
        const wob = 1 - (mk >= 1 ? 0.85 : 0);
        flyPos = [flyFrom[0] + (flyTo[0] - flyFrom[0]) * me + Math.sin(now * 0.02) * 0.012 * wob, flyFrom[1] + (flyTo[1] - flyFrom[1]) * me + Math.cos(now * 0.027) * 0.012 * wob];
        handPos = [handFrom[0] + (handTo[0] - handFrom[0]) * me, handFrom[1] + (handTo[1] - handFrom[1]) * me];
        if (act === ACTS.fly) place(flyRef.current, flyPos[0], flyPos[1]);
        if (act === ACTS.tug) place(handRef.current, handPos[0], handPos[1]);
        if (handHeld && sheet.hold) sheet.setHand(handPos[0] - sheet.hold.u, handPos[1] - sheet.hold.v);

        // เลือกสีหน้า: ผู้ใช้กำลังขยับอยู่ มาสคอตจะไม่เปลี่ยนสีหน้าเอง (นอกจากกะพริบ)
        let faceWant = 'base';
        if (forced) faceWant = forced;
        else if (act) faceWant = act[actI].face;
        else if (pressed) faceWant = (pose === 'front' ? pressFace(sheet.pull()) : sheet.pull() > 0.02 ? 'blink-half' : null) ?? 'base';
        else if (moodFace && now < moodUntil) faceWant = moodFace;
        else if (pose === 'front' && shakeFace(shake)) faceWant = shakeFace(shake);
        else if (zone && now - zoneSince > HOVER_DELAY_MS && HOVER_FACE[zone]) faceWant = HOVER_FACE[zone];
        if (faceWant !== 'base') { blinkI = -1; show(faceWant, faceWant === 'base' ? 110 : 90, now); } else {
          // กะพริบเอง: ครึ่ง → ปิด → ครึ่ง → ปกติ (ไม่กะพริบถ้าผู้ใช้ตั้งลดการเคลื่อนไหว)
          let name = 'base';
          if (set.blink && !calm) {
            if (blinkI >= 0 && now >= blinkUntil) {
              blinkI++;
              if (blinkI >= BLINK_FRAMES.length) { blinkI = -1; nextBlink = now + nextBlinkDelay(); } else blinkUntil = now + BLINK_FRAMES[blinkI][1];
            } else if (blinkI < 0 && now > nextBlink && !document.hidden) { blinkI = 0; blinkUntil = now + BLINK_FRAMES[0][1]; }
            if (blinkI >= 0) name = BLINK_FRAMES[blinkI][0];
          }
          if (name === 'base' && gazeOn && !calm && Math.abs(pu - 0.5) < 3) {
            // มองตามเคอร์เซอร์ เฉพาะเมื่อมีภาพ gaze-* ครบ 16 ทิศ (ดู hasGaze)
            name = gazeFor(pu - 0.5, pv - 0.46) ?? 'base';
          }
          show(name, name === 'base' ? 110 : 40, now);
        }

        // เอียงตัวตามแรงดึง/ท่าเล่นเอง
        const hold = sheet.hold;
        const tx = (hold ? hold.px * 0.16 : 0) + wantLean[0];
        const ty = (hold ? hold.py * 0.16 : 0) + wantLean[1];
        lvX += ((tx - leanX) * 70 - lvX * 8) * dt; lvY += ((ty - leanY) * 70 - lvY * 8) * dt;
        leanX += lvX * dt; leanY += lvY * dt;
        const leanBusy = Math.abs(lvX) + Math.abs(lvY) + Math.abs(tx - leanX) + Math.abs(ty - leanY) > 2e-4;

        // ผิว: นิ่งแล้วหยุดคำนวณ
        if (physAwake) {
          sheet.advance(dt);
          if (!sheet.holding && sheet.energy() < ENERGY_REST) { sheet.settle(); sheet.advance(0); physAwake = false; }
          dirty = true;
        }
        const fade = (now - fadeT) / fadeMs;
        if (dirty || fade < 1 || leanBusy) {
          r.draw(faceA, faceB, fade, leanX * LEAN_SCALE, leanY * LEAN_SCALE);
          dirty = fade < 1;
        }
        const busy = pressed || physAwake || handHeld || fade < 1 || blinkI >= 0 || act || leanBusy || dirty;
        if (busy) { rafId = requestAnimationFrame(tick); return; }
      }
      timerId = setTimeout(() => { timerId = 0; tick(performance.now()); }, document.hidden ? 1000 : 100);
    }

    // ภาพฐานโหลดแล้ว: เริ่มวาด ซ่อนภาพนิ่ง แล้วทยอยโหลดสีหน้าที่เหลือ
    function init(img) {
      try {
        const a = document.createElement('canvas'); a.width = a.height = 128;
        const ac = a.getContext('2d', { willReadFrequently: true });
        ac.drawImage(img, 0, 0, 128, 128);
        alpha = ac.getImageData(0, 0, 128, 128).data;
      } catch { alpha = null; }
      const b = canvas.getBoundingClientRect();
      r.resize(b.width || 1, b.height || 1);
      sheet.advance(0);
      if (!r.draw('base', 'base', 1, 0, 0)) { onFail?.(); return; }
      ready = true;
      onReady?.();
      const rest = Object.keys(images).filter((n) => n !== 'base' && n !== 'front');
      rest.sort((x, y) => (FRONT_ORDER.indexOf(x) + 1 || 99) - (FRONT_ORDER.indexOf(y) + 1 || 99));
      for (const n of rest) want(n);
    }

    want('base', true);
    kick();

    return () => {
      alive = false;
      cancelAnimationFrame(rafId); clearTimeout(timerId);
      host.removeEventListener('pointerdown', onDown);
      host.removeEventListener('pointermove', onMove);
      host.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('pointerup', release);
      window.removeEventListener('pointercancel', release);
      canvas.removeEventListener('webglcontextlost', onLost);
      unsubscribe(); io.disconnect(); ro.disconnect();
      dropActLock(id);
      if (apiRef) apiRef.current = null;
      host.style.cursor = '';
      r.dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pose, size, idleActs]);

  return (
    <span className="mascot-sheet" style={{ ...imageStyle, aspectRatio: `${set.canvas[0]} / ${set.canvas[1]}` }} aria-hidden="true">
      <canvas ref={canvasRef} className="mascot-gl" />
      <svg ref={flyRef} className="mascot-fly" viewBox="0 0 32 32"><path className="wing" d="M15 15C12 9.500 4.500 8.500 2 13c2.500 4.500 10 4.500 13 2z" /><path className="wing r" d="M17 15c3-5.500 10.500-6.500 13-2-2.500 4.500-10 4.500-13 2z" /><ellipse cx="16" cy="19.500" rx="4" ry="6.500" /><circle cx="16" cy="11.500" r="3.300" /></svg>
      <svg ref={handRef} className="mascot-hand" viewBox="0 0 32 32"><path className="open" d="M10.500 16.500V8.200a1.800 1.800 0 0 1 3.600 0V14v-8a1.800 1.800 0 0 1 3.600 0V14 7a1.800 1.800 0 0 1 3.600 0v8-5a1.800 1.800 0 0 1 3.600 0v10.500c0 5-3.400 8.500-8.400 8.500-3.600 0-5.700-1.600-7.600-4.600l-3.500-5.600c-.6-1 .1-2.200 1.200-2.400 1-.2 1.900.2 2.600 1z" /><path className="grab" d="M10.500 17v-3.300a1.800 1.800 0 0 1 3.600 0V14v-1.800a1.800 1.800 0 0 1 3.600 0V14v-1.300a1.800 1.800 0 0 1 3.600 0V14v-.3a1.800 1.800 0 0 1 3.600 0v6.800c0 5-3.400 8.500-8.400 8.500-3.600 0-5.700-1.600-7.600-4.600l-2.300-3.700c-.6-1 .1-2.200 1.200-2.400 1-.2 1.900.2 2.700 1z" /></svg>
    </span>
  );
}
