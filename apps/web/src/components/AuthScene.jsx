import { useMemo } from 'react';
import { useLanguage } from '../lib/language.jsx';
import { ROUTE, STOPS, contours } from '../lib/authScene.js';
import { prefersReducedMotion } from '../lib/mascot.js';
import './authScene.css';

// ไอคอนเส้นขนาด 24 หน่วย วาดเอง (ไม่ใช้ภาพจากที่อื่น)
const ICONS = {
  stay: <><path d="M3 19V8m0 7h18v4m0-4v-1.5a3.5 3.5 0 0 0-3.5-3.5H10v5" /><circle cx="6.5" cy="12" r="1.6" /></>,
  cafe: <path d="M4 8h12v5a6 6 0 0 1-12 0V8Zm12 1.5h1.5a2.5 2.5 0 0 1 0 5H16M7 3.5v2m3-2v2M3 21h15" />,
  temple: <path d="M12 2.5 13.4 6h-2.8L12 2.5Zm-2.2 4h4.4l1 4.5H8.8l1-4.5ZM7 11.5h10l1.2 5H5.8L7 11.5ZM4.5 17h15v3.5h-15V17Z" />,
  mountain: <><path d="m2.5 20 7-11.5 4 6.3 2.4-3.6 5.6 8.8H2.5Z" /><path d="m7.6 11.6 1.9-3.1 1.9 3" /></>,
  beach: <><path d="M12 5a8 8 0 0 1 8 8H4a8 8 0 0 1 8-8Zm0 8v6" /><path d="M3 20.5c2-1.3 4-1.3 6 0s4 1.3 6 0 4-1.3 6 0" /></>,
};

function Stop({ id, label, at, delay }) {
  const [x, y] = at;
  const w = Math.max(54, label.length * 11 + 22);
  return (
    <g className={`as-stop as-stop-${id}`} transform={`translate(${x} ${y})`}>
      <g className="as-stop-float" style={{ animationDelay: `${delay}s, ${delay + 0.6}s` }}>
      <circle className="as-stop-halo" r="34" style={{ animationDelay: `${delay * 2}s` }} />
      <circle className="as-stop-badge" r="25" />
      <g className="as-stop-icon" transform="translate(-12 -12)">{ICONS[id]}</g>
      <g className="as-stop-label" transform={`translate(${-w / 2} 34)`}>
        <rect width={w} height="24" rx="12" />
        <text x={w / 2} y="16.5" textAnchor="middle">{label}</text>
      </g>
      </g>
    </g>
  );
}

// พื้นหลังแผงมาสคอต: แผนที่ทริปมีเส้นชั้นความสูง วงรัศมีรอบที่พัก เส้นทางไปที่เที่ยว เครื่องบินกระดาษ และเมฆ
// variant "day" (หน้าเข้าสู่ระบบ) กับ "dusk" (หน้าสมัคร) สลับกันแบบค่อย ๆ จาง ไม่เปลี่ยนโครง
// ทุกอย่างเป็นของตกแต่ง ซ่อนจากโปรแกรมอ่านหน้าจอ ผู้ใช้ที่ตั้งลดการเคลื่อนไหวเห็นภาพนิ่ง (ดู auth-v2.css)
export default function AuthScene({ variant = 'day' }) {
  const { t } = useLanguage();
  const lines = useMemo(() => contours(), []);
  const still = useMemo(() => prefersReducedMotion(), []);
  const stops = [
    ['cafe', t('คาเฟ่', 'Cafés'), 0.2], ['temple', t('วัด', 'Temples'), 0.5],
    ['mountain', t('ภูเขา', 'Mountains'), 0.8], ['beach', t('ทะเล', 'Beaches'), 1.1],
  ];
  return (
    <div className={`as-scene as-${variant}`} aria-hidden="true">
      <svg className="as-svg" viewBox="0 0 720 1000" preserveAspectRatio="xMidYMax slice" focusable="false">
        <defs>
          <linearGradient id="as-sky-day" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#467856" /><stop offset=".55" stopColor="#3d6a4b" /><stop offset="1" stopColor="#2f5a3c" />
          </linearGradient>
          <linearGradient id="as-sky-dusk" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor="#24402f" /><stop offset=".5" stopColor="#35573f" /><stop offset=".86" stopColor="#7a6a3c" /><stop offset="1" stopColor="#b9773a" />
          </linearGradient>
          <radialGradient id="as-sun" cx=".5" cy=".5" r=".5">
            <stop offset="0" stopColor="#ffe3a3" stopOpacity=".95" /><stop offset=".35" stopColor="#ffc453" stopOpacity=".55" /><stop offset="1" stopColor="#ffc453" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="as-glow" cx=".5" cy="1" r=".75">
            <stop offset="0" stopColor="#ffb25c" stopOpacity=".55" /><stop offset="1" stopColor="#ffb25c" stopOpacity="0" />
          </radialGradient>
          <radialGradient id="as-floor" cx=".5" cy=".5" r=".5">
            <stop offset="0" stopColor="#f5f3ed" stopOpacity=".16" /><stop offset="1" stopColor="#f5f3ed" stopOpacity="0" />
          </radialGradient>
        </defs>

        <rect className="as-sky as-sky-day" width="720" height="1000" fill="url(#as-sky-day)" />
        <rect className="as-sky as-sky-dusk" width="720" height="1000" fill="url(#as-sky-dusk)" />
        <rect className="as-dusk-glow" x="-120" y="560" width="960" height="440" fill="url(#as-glow)" />

        <g className="as-layer as-far">
          <g className="as-grid">
            {Array.from({ length: 9 }, (_, i) => <line key={`v${i}`} x1={i * 90} y1="0" x2={i * 90} y2="1000" />)}
            {Array.from({ length: 12 }, (_, i) => <line key={`h${i}`} x1="0" y1={i * 90} x2="720" y2={i * 90} />)}
          </g>
          <circle className="as-sun" cx="610" cy="330" r="120" fill="url(#as-sun)" />
          <g className="as-moon" transform="translate(600 320)">
            <circle r="26" /><circle className="as-moon-cut" cx="11" cy="-7" r="23" />
          </g>
          <g className="as-stars">
            {[[470, 200], [560, 170], [660, 230], [520, 380], [690, 410], [420, 280], [640, 140], [380, 150]].map(([x, y], i) => (
              <circle key={i} cx={x} cy={y} r={i % 3 ? 1.6 : 2.4} style={{ animationDelay: `${i * 0.7}s` }} />
            ))}
          </g>
          <g className="as-contours">{lines.map((d, i) => <path key={i} d={d} />)}</g>
        </g>

        <g className="as-layer as-mid">
          <g className="as-cloud as-cloud-1"><circle cx="0" cy="0" r="22" /><circle cx="26" cy="-10" r="28" /><circle cx="56" cy="2" r="20" /><rect x="-4" y="0" width="64" height="20" rx="10" /></g>
          <g className="as-cloud as-cloud-2"><circle cx="0" cy="0" r="16" /><circle cx="20" cy="-8" r="21" /><circle cx="42" cy="0" r="15" /><rect x="-2" y="0" width="47" height="15" rx="7" /></g>
          <g className="as-cloud as-cloud-3"><circle cx="0" cy="0" r="13" /><circle cx="16" cy="-6" r="17" /><circle cx="33" cy="0" r="12" /><rect x="-2" y="0" width="37" height="12" rx="6" /></g>
          <g className="as-rings">
            <ellipse cx="360" cy="912" rx="170" ry="52" />
            <ellipse cx="360" cy="912" rx="290" ry="92" />
            <ellipse cx="360" cy="912" rx="430" ry="140" />
          </g>
          <g className="as-ring-tags">
            <text x="532" y="903">5 {t('กม.', 'km')}</text>
            <text x="652" y="866">10 {t('กม.', 'km')}</text>
          </g>
          <ellipse cx="360" cy="912" rx="210" ry="60" fill="url(#as-floor)" />
          <path className="as-route-shadow" d={ROUTE} />
          <path className="as-route" d={ROUTE} />
          <g className="as-plane" transform={still ? 'translate(250 520) rotate(-25)' : undefined}>
            <path d="M-11-7 13 0-11 7-6 0Z" />
            <path className="as-plane-fold" d="M-6 0 13 0" />
            {!still && <animateMotion dur="16s" repeatCount="indefinite" rotate="auto" path={ROUTE} />}
          </g>
        </g>

        <g className="as-layer as-near">
          {stops.map(([id, label, delay]) => <Stop key={id} id={id} label={label} at={STOPS[id]} delay={delay} />)}
        </g>
      </svg>
    </div>
  );
}
