import { useEffect, useRef, useState } from 'react';
import { useLanguage } from '../lib/language.jsx';
import { BLINK_FRAMES, POSE_SETS, nextBlinkDelay, poseFrame, poseUrl, preload, prefersReducedMotion } from '../lib/mascot.js';
import { webglSupported } from '../lib/mascotGl.js';
import MascotSheet from './MascotSheet.jsx';
import front from '../assets/mascot/front.webp';
import wave from '../assets/mascot/wave.webp';
import happy from '../assets/mascot/happy.webp';
import think from '../assets/mascot/think.webp';

// มาสคอต "น้องทริป" แมวส้มนักสำรวจ
// mood: 'wave' โบกมือ, 'happy' ยิ้มตาปิด, 'think' สงสัย, 'front' ยืนถือกล้อง
// ขยับเองตลอด (โยกตัว หายใจ) เด้งเมื่อชี้ และกระโดดดีใจเมื่อแตะ
// mood="front" ใช้ชุดสีหน้า v2 (23 แบบ บนภาพฐานเดียวกัน): กะพริบตาเอง ชี้แล้วตาเป็นดาว แตะแล้วยิ้ม
// แตะรัว ๆ จะโอ๊ยแล้วโกรธ ว่างนานหาว และหน้าที่เรียกใช้กำหนดสีหน้าเองได้ด้วย prop expression
// wave และ think มีชุดของตัวเอง (expressions-v2/<ท่า>): กะพริบตาเอง แตะแล้วยิ้มกว้าง
// happy ตาหยียิ้มอยู่แล้วจึงไม่กะพริบเอง แตะแล้วลืมตามองครู่หนึ่ง
// ทุกท่าสลับทั้งภาพผ่าน src ภาพเต็มของท่าเดียวกันขนาดผืนเท่ากัน กรอบจึงไม่ขยับ
// ถ้าผู้ใช้ตั้งลดการเคลื่อนไหว จะไม่กะพริบ/หาวเอง (สีหน้าตอบสนองการกดยังทำงาน)
// เล่นกับมาสคอตได้ (interactive): พอผู้ใช้ชี้/แตะ (ตัวใหญ่เริ่มเองหลังโหลดเสร็จ) จะเปลี่ยนไปใช้ MascotSheet ที่วาดด้วย WebGL
// จับดึงให้ตัวยืดเหมือนแป้ง ชี้/แตะแต่ละจุดได้สีหน้าต่างกัน เขย่าเมาส์แล้วปั่นป่วน ปล่อยว่างนานจะเล่นท่าเอง
// ถ้าเบราว์เซอร์ไม่มี WebGL หรือโหลดไม่สำเร็จ ก็ใช้ภาพนิ่งสลับสีหน้าแบบเดิมทั้งหมด (ด้านล่าง)
const POSES = { front, wave, happy, think }; // ภาพสำรองเฉพาะ mood ที่ไม่รู้จัก
const IDLE_YAWN_MS = 25000;
const REACT_MS = 1100;

export default function Mascot({ size = 120, mood = 'wave', className = '', title, interactive = true, expression }) {
  const { t } = useLanguage();
  const name = title ?? t('น้องทริป', 'NongTrip');
  const pose = POSE_SETS[mood] ? mood : null; // null = mood นอกชุด ใช้ภาพนิ่งเดิม
  const set = pose ? POSE_SETS[pose] : null;
  const expressive = pose !== null;
  const [joy, setJoy] = useState(false);
  const [face, setFace] = useState(null); // ชื่อสีหน้าชั่วคราวจากการกะพริบ/ตอบสนอง
  const timer = useRef(null);
  const faceTimer = useRef(null);
  const taps = useRef({ n: 0, at: 0 });
  const busyFace = useRef(false);
  const rootRef = useRef(null);
  const apiRef = useRef(null);
  const mountedAt = useRef(0);
  const failed = useRef(false);
  const [active, setActive] = useState(false); // เอนจินเล่นเริ่มทำงานแล้ว
  const [engine, setEngine] = useState('loading'); // 'loading' | 'ready' | 'failed'
  const playing = active && engine !== 'failed';
  const drawing = active && engine === 'ready'; // canvas วาดอยู่ ภาพนิ่งถูกซ่อน
  useEffect(() => () => { clearTimeout(timer.current); clearTimeout(faceTimer.current); }, []);
  // เริ่มเอนจินเล่น: ตัวใหญ่เริ่มเองหลังโหลดหน้า ตัวเล็กรอจนผู้ใช้ชี้/แตะ (ประหยัดบริบท WebGL ของหน้าที่มีมาสคอตหลายตัว)
  const activate = () => {
    if (!interactive || !expressive || active || failed.current) return;
    if (!webglSupported()) { failed.current = true; return; }
    setActive(true);
  };
  useEffect(() => {
    mountedAt.current = performance.now();
    if (!interactive || !expressive || size < 150) return undefined;
    const h = setTimeout(activate, 800);
    return () => clearTimeout(h);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pose, interactive]);
  // ท่าเล่นเองเฉพาะ front ตัวใหญ่ (หน้าแรก เข้าสู่ระบบ) ไม่ให้ตัวเล็กหลายตัวเล่นพร้อมกัน
  const idleActs = pose === 'front' && size >= 150;
  const jump = () => {
    if (timer.current !== null) return;
    setJoy(true);
    timer.current = setTimeout(() => { setJoy(false); timer.current = null; }, 900);
  };
  // เปลี่ยนท่าระหว่างที่ยังมีสีหน้าชั่วคราวค้างอยู่ ให้เคลียร์ทิ้ง ไม่เอาชื่อสีหน้าของท่าเก่าไปใช้กับท่าใหม่
  useEffect(() => { clearTimeout(faceTimer.current); busyFace.current = false; setFace(null); }, [pose]);

  const showFace = (next, ms) => {
    clearTimeout(faceTimer.current);
    busyFace.current = true;
    setFace(next);
    faceTimer.current = setTimeout(() => { busyFace.current = false; setFace(null); }, ms);
  };

  // กะพริบตา + หาวเมื่อว่างนาน
  useEffect(() => {
    if (!set?.blink || prefersReducedMotion() || playing) return undefined;
    preload(BLINK_FRAMES.map(([n]) => n), pose);
    let stop = false;
    let blinkTimer;
    let yawnTimer;
    const sleep = (ms) => new Promise((resolve) => { blinkTimer = setTimeout(resolve, ms); });
    (async () => {
      while (!stop) {
        await sleep(nextBlinkDelay());
        if (stop || busyFace.current || document.hidden) continue;
        for (const [frame, ms] of BLINK_FRAMES) {
          if (stop || busyFace.current) break;
          setFace(frame);
          await sleep(ms);
        }
        if (!busyFace.current) setFace(null);
      }
    })();
    const arm = () => {
      clearTimeout(yawnTimer);
      yawnTimer = setTimeout(() => { preload(['yawn'], pose); if (!busyFace.current && !document.hidden) showFace('yawn', 1800); arm(); }, IDLE_YAWN_MS);
    };
    if (set.yawn) {
      arm();
      window.addEventListener('pointerdown', arm);
      window.addEventListener('keydown', arm);
    }
    return () => {
      stop = true;
      clearTimeout(blinkTimer);
      clearTimeout(yawnTimer);
      window.removeEventListener('pointerdown', arm);
      window.removeEventListener('keydown', arm);
    };
  }, [pose, playing]);

  const cheer = () => {
    if (!interactive) return;
    if (expressive) {
      const now = Date.now();
      taps.current = { n: now - taps.current.at < 1500 ? taps.current.n + 1 : 1, at: now };
      showFace(set.tap(taps.current.n), REACT_MS);
    }
    if (timer.current !== null) return;
    setJoy(true);
    timer.current = setTimeout(() => { setJoy(false); timer.current = null; }, 900);
  };
  const warm = () => {
    activate();
    if (!expressive || !interactive || playing) return;
    preload(pose === 'front' ? ['star-eyes', 'grin', 'ouch', 'angry'] : [set.tap(1)], pose);
  };
  const hoverIn = () => { if (playing) return; activate(); if (set?.hover && interactive && !busyFace.current) { warm(); showFace(set.hover, 1600); } };
  // คลิกด้วยเมาส์/นิ้วเอนจินจัดการเองตอนปล่อยมือ (แยกแตะกับดึงได้) เหลือเฉพาะปุ่มคีย์บอร์ด (detail 0) ที่ต้องแตะแทน
  const onClick = (e) => {
    if (engine === 'ready' && active) { if (e.detail === 0) apiRef.current?.tapKey(); return; }
    cheer();
  };
  const src = expressive
    ? poseUrl(pose, expression ?? face ?? 'base')
    : (joy ? happy : (POSES[mood] ?? wave));
  const geometry = expressive ? poseFrame(pose) : null;
  const Element = interactive ? 'button' : 'span';

  return (
    <Element
      type={interactive ? 'button' : undefined}
      ref={rootRef}
      className={`mascot mascot-${mood} ${joy ? 'is-joy' : ''} ${interactive ? 'is-live' : ''} ${drawing ? 'is-play' : ''} ${className}`}
      style={{ width: size }}
      onClick={interactive ? onClick : undefined}
      onPointerEnter={interactive && expressive ? hoverIn : undefined}
      onPointerDown={interactive && expressive ? activate : undefined}
      onFocus={interactive && expressive ? warm : undefined}
      aria-label={interactive ? `${name || t('น้องทริป', 'NongTrip')} (${t('แตะเพื่อทักทาย', 'Say hello')})` : undefined}
    >
      <span className="mascot-body">
        {expressive
          ? (
            <span className="mascot-frame" style={geometry.frame}>
              <img src={src} style={drawing ? { ...geometry.image, visibility: 'hidden' } : geometry.image} alt={interactive ? '' : name} draggable="false" />
              {playing && (
                <MascotSheet
                  key={pose}
                  pose={pose}
                  size={size}
                  imageStyle={geometry.image}
                  forcedFace={expression ?? null}
                  idleActs={idleActs}
                  mountedAt={mountedAt.current}
                  reduced={prefersReducedMotion()}
                  hostRef={rootRef}
                  apiRef={apiRef}
                  onReady={() => setEngine('ready')}
                  onFail={() => { failed.current = true; setEngine('failed'); setActive(false); }}
                  onTap={jump}
                />
              )}
            </span>
          )
          : <img src={src} alt={interactive ? '' : name} draggable="false" />}
      </span>
      <span className="mascot-shadow" aria-hidden="true" />
    </Element>
  );
}
