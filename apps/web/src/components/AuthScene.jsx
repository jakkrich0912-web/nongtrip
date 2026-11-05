import { useMemo } from 'react';
import { prefersReducedMotion } from '../lib/mascot.js';
import './authScene.css';

// พื้นหลังแผงมาสคอตของหน้าเข้าสู่ระบบ/สมัคร: ภาพวิว assets/mascot/auth-backgrounds/ (ไม่มีข้อความหรือมาสคอตในภาพ)
// variant "login" ป่าและทิวเขาแสงเช้า "signup" ทะเลสาบและภูเขาหินปูน สลับด้วยการจางทับกัน
// ภาพใส่ผ่าน CSS ใน media query จอที่ไม่แสดงภาพนั้นจึงไม่โหลด (จอเล็กใช้ภาพรุ่นมือถือ)
// ชั้นเขียวเข้มด้านบนกันข้อความจมหาย เครื่องบินกระดาษบินผ่านท้องฟ้า (ปิดเมื่อผู้ใช้ตั้งลดการเคลื่อนไหว)
const PATH = 'M-60,470 C140,420 300,500 460,445 S700,400 820,450';

export default function AuthScene({ variant = 'login' }) {
  const still = useMemo(() => prefersReducedMotion(), []);
  return (
    <div className={`as-scene as-${variant}`} aria-hidden="true">
      <div className="as-bg as-bg-login" />
      <div className="as-bg as-bg-signup" />
      <div className="as-shade" />
      {!still && (
        <svg className="as-sky" viewBox="0 0 720 1000" preserveAspectRatio="xMidYMin slice" focusable="false">
          <path className="as-trail" d={PATH} />
          <g className="as-plane">
            <path d="M-11-7 13 0-11 7-6 0Z" />
            <path className="as-plane-fold" d="M-6 0 13 0" />
            <animateMotion dur="14s" repeatCount="indefinite" rotate="auto" path={PATH} />
          </g>
        </svg>
      )}
    </div>
  );
}
