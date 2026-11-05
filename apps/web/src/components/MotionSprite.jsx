import { useEffect, useRef, useState } from 'react';
import { MOTIONS, frameIndex, spriteBox } from '../lib/mascotFrames.js';
import './motionSprite.css';

// เล่นภาพเคลื่อนไหวหนึ่งชุดแทนมาสคอตนิ่ง ในกล่องเดียวกับมาสคอตขนาด size (ผู้เรียกซ่อนมาสคอตนิ่งเอง)
// ใช้ requestAnimationFrame: แท็บถูกซ่อนแล้วหยุดเอง และนับเวลาข้ามช่วงที่ซ่อนไม่เกิน 100 ms ต่อครั้ง
// dir < 0 สะท้อนทั้งภาพรอบจุดพื้น loops จำนวนรอบ (Infinity วนไปเรื่อย ๆ) เล่นครบแล้วเรียก onEnd
export default function MotionSprite({ name, size, dir = 1, fps, loops = Infinity, onEnd }) {
  const motion = MOTIONS[name];
  const [index, setIndex] = useState(0);
  const end = useRef(onEnd);
  end.current = onEnd;
  const rate = fps ?? motion?.fps;
  useEffect(() => {
    if (!motion) return undefined;
    let alive = true;
    let raf = 0;
    let last = null;
    let elapsed = 0;
    const tick = (now) => {
      if (!alive) return;
      if (last !== null) elapsed += Math.min(now - last, 100);
      last = now;
      const k = frameIndex(elapsed, rate, motion.frames.length, loops);
      if (k < 0) { end.current?.(); return; }
      setIndex(k);
      raf = requestAnimationFrame(tick);
    };
    setIndex(0);
    raf = requestAnimationFrame(tick);
    return () => { alive = false; cancelAnimationFrame(raf); };
  }, [motion, rate, loops]);
  if (!motion) return null;
  const box = spriteBox(size, motion);
  return (
    <img className="ms-sprite" src={motion.frames[index] ?? motion.frames[0]} alt="" aria-hidden="true" draggable="false"
      style={{
        left: box.left, top: box.top, width: box.width, height: box.height,
        transformOrigin: `${box.originX}px ${box.originY}px`, transform: dir < 0 ? 'scaleX(-1)' : undefined,
      }} />
  );
}
