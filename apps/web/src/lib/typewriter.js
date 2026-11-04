// พิมพ์คำตอบทีละตัวอักษรแบบแอปแชต: ตัดตามตัวอักษรที่มนุษย์เห็น (สระ/วรรณยุกต์ไทยไม่แยกจากพยัญชนะ)
// ข้อความยิ่งค้างมาก ยิ่งเร่ง จึงไม่ช้ากว่าสตรีมจริง
import { useEffect, useRef, useState } from 'react';
import { prefersReducedMotion } from './mascot.js';

const seg = typeof Intl !== 'undefined' && Intl.Segmenter ? new Intl.Segmenter('th', { granularity: 'grapheme' }) : null;

// ตำแหน่งตัดที่ปลอดภัยทุกตำแหน่งของข้อความ (สิ้นสุดของแต่ละตัวอักษร)
export function graphemeEnds(text) {
  if (!text) return [];
  if (!seg) return Array.from({ length: text.length }, (_, i) => i + 1);
  const out = [];
  for (const { index, segment } of seg.segment(text)) out.push(index + segment.length);
  return out;
}

// ก้าวต่อเฟรม: อย่างน้อย 1 ตัว ข้อความค้างมากเร่งให้ทันภายในราว 12 เฟรม
export const stepFor = (remaining) => Math.max(1, Math.ceil(remaining / 12));

// คืนข้อความที่ควรแสดงตอนนี้ และกำลังพิมพ์อยู่ไหม
// instant = แสดงทั้งหมดทันที (คำตอบเก่าจากประวัติ ตอบเสร็จก่อนเปิดหน้านี้ หรือผู้ใช้ตั้งลดการเคลื่อนไหว)
export function useTypewriter(text, instant) {
  const [count, setCount] = useState(() => (instant ? Infinity : 0));
  const ends = useRef([]);
  ends.current = graphemeEnds(text);
  const reduced = useRef(prefersReducedMotion());
  const total = ends.current.length;
  const showAll = instant || reduced.current;
  useEffect(() => {
    if (showAll || count >= total) return undefined;
    const id = requestAnimationFrame(() => setCount((c) => Math.min(total, (Number.isFinite(c) ? c : total) + stepFor(total - c))));
    return () => cancelAnimationFrame(id);
  }, [count, total, showAll]);
  if (showAll || count >= total) return [text, false];
  return [text.slice(0, count > 0 ? ends.current[count - 1] : 0), true];
}
