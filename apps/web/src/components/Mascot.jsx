import { useEffect, useRef, useState } from 'react';
import { useLanguage } from '../lib/language.jsx';
import { BLINK_FRAMES, expressionUrl, nextBlinkDelay, preload, prefersReducedMotion, tapExpression } from '../lib/mascot.js';
import front from '../assets/mascot/front.webp';
import wave from '../assets/mascot/wave.webp';
import happy from '../assets/mascot/happy.webp';
import think from '../assets/mascot/think.webp';

// มาสคอต "น้องทริป" แมวส้มนักสำรวจ
// mood: 'wave' โบกมือ, 'happy' ยิ้มตาปิด, 'think' สงสัย, 'front' ยืนถือกล้อง
// ขยับเองตลอด (โยกตัว หายใจ) เด้งเมื่อชี้ และกระโดดดีใจเมื่อแตะ
// mood="front" ใช้ชุดสีหน้า v2 (23 แบบ บนภาพฐานเดียวกัน): กะพริบตาเอง ชี้แล้วตาเป็นดาว แตะแล้วยิ้ม
// แตะรัว ๆ จะโอ๊ยแล้วโกรธ ว่างนานหาว และหน้าที่เรียกใช้กำหนดสีหน้าเองได้ด้วย prop expression
// ท่าอื่น (wave happy think) เป็นท่าเต็มตัวคนละภาพ จึงไม่สลับสีหน้า
// ถ้าผู้ใช้ตั้งลดการเคลื่อนไหว จะไม่กะพริบ/หาวเอง (สีหน้าตอบสนองการกดยังทำงาน)
const POSES = { front, wave, happy, think };
const IDLE_YAWN_MS = 25000;
const REACT_MS = 1100;

export default function Mascot({ size = 120, mood = 'wave', className = '', title, interactive = true, expression }) {
  const { t } = useLanguage();
  const name = title ?? t('น้องทริป', 'NongTrip');
  const expressive = mood === 'front';
  const [joy, setJoy] = useState(false);
  const [face, setFace] = useState(null); // ชื่อสีหน้าชั่วคราวจากการกะพริบ/ตอบสนอง
  const timer = useRef(null);
  const faceTimer = useRef(null);
  const taps = useRef({ n: 0, at: 0 });
  const busyFace = useRef(false);
  useEffect(() => () => { clearTimeout(timer.current); clearTimeout(faceTimer.current); }, []);

  const showFace = (next, ms) => {
    clearTimeout(faceTimer.current);
    busyFace.current = true;
    setFace(next);
    faceTimer.current = setTimeout(() => { busyFace.current = false; setFace(null); }, ms);
  };

  // กะพริบตา + หาวเมื่อว่างนาน
  useEffect(() => {
    if (!expressive || prefersReducedMotion()) return undefined;
    preload(BLINK_FRAMES.map(([n]) => n));
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
      yawnTimer = setTimeout(() => { preload(['yawn']); if (!busyFace.current && !document.hidden) showFace('yawn', 1800); arm(); }, IDLE_YAWN_MS);
    };
    arm();
    window.addEventListener('pointerdown', arm);
    window.addEventListener('keydown', arm);
    return () => {
      stop = true;
      clearTimeout(blinkTimer);
      clearTimeout(yawnTimer);
      window.removeEventListener('pointerdown', arm);
      window.removeEventListener('keydown', arm);
    };
  }, [expressive]);

  const cheer = () => {
    if (!interactive) return;
    if (expressive) {
      const now = Date.now();
      taps.current = { n: now - taps.current.at < 1500 ? taps.current.n + 1 : 1, at: now };
      showFace(tapExpression(taps.current.n), REACT_MS);
    }
    if (timer.current !== null) return;
    setJoy(true);
    timer.current = setTimeout(() => { setJoy(false); timer.current = null; }, 900);
  };
  const warm = () => {
    if (!expressive || !interactive) return;
    preload(['star-eyes', 'grin', 'ouch', 'angry']);
  };
  const hoverIn = () => { if (expressive && interactive && !busyFace.current) { warm(); showFace('star-eyes', 1600); } };
  const src = expressive
    ? expressionUrl(expression ?? face ?? 'front')
    : (joy ? happy : (POSES[mood] ?? wave));
  const Element = interactive ? 'button' : 'span';

  return (
    <Element
      type={interactive ? 'button' : undefined}
      className={`mascot mascot-${mood} ${joy ? 'is-joy' : ''} ${interactive ? 'is-live' : ''} ${className}`}
      style={{ width: size }}
      onClick={interactive ? cheer : undefined}
      onPointerEnter={interactive && expressive ? hoverIn : undefined}
      onFocus={interactive && expressive ? warm : undefined}
      aria-label={interactive ? `${name || t('น้องทริป', 'NongTrip')} (${t('แตะเพื่อทักทาย', 'Say hello')})` : undefined}
    >
      <span className="mascot-body">
        {expressive
          ? <span className="mascot-frame"><img src={src} alt={interactive ? '' : name} draggable="false" /></span>
          : <img src={src} alt={interactive ? '' : name} draggable="false" />}
      </span>
      <span className="mascot-shadow" aria-hidden="true" />
    </Element>
  );
}
