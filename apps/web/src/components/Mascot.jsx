import { useEffect, useRef, useState } from 'react';
import { useLanguage } from '../lib/language.jsx';
import front from '../assets/mascot/front.webp';
import wave from '../assets/mascot/wave.webp';
import happy from '../assets/mascot/happy.webp';
import think from '../assets/mascot/think.webp';

// มาสคอต "น้องทริป" แมวส้มนักสำรวจ
// mood: 'wave' โบกมือ, 'happy' ยิ้มตาปิด, 'think' สงสัย, 'front' ยืนถือกล้อง
// ขยับเองตลอด (โยกตัว หายใจ) เด้งเมื่อชี้ และกระโดดดีใจเมื่อแตะ
const POSES = { front, wave, happy, think };

export default function Mascot({ size = 120, mood = 'wave', className = '', title, interactive = true }) {
  const { t } = useLanguage();
  const name = title ?? t('น้องทริป', 'NongTrip');
  const [joy, setJoy] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const cheer = () => {
    if (!interactive || timer.current !== null) return;
    setJoy(true);
    timer.current = setTimeout(() => { setJoy(false); timer.current = null; }, 900);
  };
  const src = joy ? happy : (POSES[mood] ?? wave);
  const Element = interactive ? 'button' : 'span';

  return (
    <Element
      type={interactive ? 'button' : undefined}
      className={`mascot mascot-${mood} ${joy ? 'is-joy' : ''} ${interactive ? 'is-live' : ''} ${className}`}
      style={{ width: size }}
      onClick={interactive ? cheer : undefined}
      aria-label={interactive ? `${name || t('น้องทริป', 'NongTrip')} (${t('แตะเพื่อทักทาย', 'Say hello')})` : undefined}
    >
      <span className="mascot-body">
        <img src={src} alt={interactive ? '' : name} draggable="false" />
      </span>
      <span className="mascot-shadow" aria-hidden="true" />
    </Element>
  );
}
