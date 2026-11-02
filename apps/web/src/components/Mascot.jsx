import { useState } from 'react';
import front from '../assets/mascot/front.webp';
import wave from '../assets/mascot/wave.webp';
import happy from '../assets/mascot/happy.webp';
import think from '../assets/mascot/think.webp';

// มาสคอต "น้องทริป" แมวส้มนักสำรวจ
// mood: 'wave' โบกมือ, 'happy' ยิ้มตาปิด, 'think' สงสัย, 'front' ยืนถือกล้อง
// ขยับเองตลอด (โยกตัว หายใจ) เด้งเมื่อชี้ และกระโดดดีใจเมื่อแตะ
const POSES = { front, wave, happy, think };

export default function Mascot({ size = 120, mood = 'wave', className = '', title = 'น้องทริป', interactive = true }) {
  const [joy, setJoy] = useState(false);
  const cheer = () => {
    if (!interactive || joy) return;
    setJoy(true);
    setTimeout(() => setJoy(false), 900);
  };
  const src = joy ? happy : (POSES[mood] ?? wave);

  return (
    <span
      className={`mascot mascot-${mood} ${joy ? 'is-joy' : ''} ${interactive ? 'is-live' : ''} ${className}`}
      style={{ width: size }}
      onClick={cheer}
      onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') cheer(); }}
      role={interactive ? 'button' : undefined}
      tabIndex={interactive ? 0 : undefined}
      aria-label={interactive && title ? `${title} (แตะเพื่อทักทาย)` : undefined}
    >
      <span className="mascot-body">
        <img src={src} alt={interactive ? '' : title} draggable="false" />
      </span>
      <span className="mascot-shadow" aria-hidden="true" />
    </span>
  );
}
