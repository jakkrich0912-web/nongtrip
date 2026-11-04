import { useEffect, useRef, useState } from 'react';
import Mascot from './Mascot.jsx';
import { prefersReducedMotion } from '../lib/mascot.js';
import './mascotStage.css';
import { HOP_MS, PEEK_MS, STEP_MS, cueOf, pickAct, restAfter, roam, walkPlan, walkTarget } from '../lib/mascotMotion.js';

// เวทีของน้องทริป: ใช้มาสคอตตัวเดิม (มองตามเคอร์เซอร์ จับดึงเล่นได้เหมือนเดิม) แล้วเพิ่มท่าทางเอง
// เดินเตาะแตะไปมา กระโดดดึ๋ง ชะโงกดู ยืนหายใจ และตอบสนองฟอร์ม (cue) เช่น ปิดตาตอนพิมพ์รหัสผ่าน
// ผู้ใช้กำลังจับเล่นหรือแท็บถูกซ่อนจะหยุดเดินก่อน ผู้ใช้ที่ตั้งลดการเคลื่อนไหวจะยืนนิ่งที่กลาง
// formSide: ฟอร์มอยู่ฝั่งไหนของมาสคอต ('right' | 'left') ใช้หันไปชะโงกดูตอนผู้ใช้พิมพ์
// children: กล่องพูด วางเหนือหัวและเดินตามตัว หันไปฝั่งที่มีที่ว่างมากกว่าเสมอ (ไม่ล้นขอบแผง)
export default function MascotStage({ size = 260, cue = null, formSide = 'right', title, children }) {
  const stage = useRef(null);
  const body = useRef(null);
  const xRef = useRef(0);
  const last = useRef(null);
  const holding = useRef(false);
  const cueBusy = useRef(false);
  const [move, setMove] = useState({ x: 0, act: 'rest', dir: 1, ms: 0, steps: 0 });
  const [face, setFace] = useState(null);
  const reduced = useRef(prefersReducedMotion()).current;
  const towardForm = formSide === 'right' ? 1 : -1;

  // ท่าทางเอง: สุ่มท่าแล้วพักสลับกันไปเรื่อย ๆ
  useEffect(() => {
    if (reduced) return undefined;
    let alive = true;
    let timer;
    const later = (fn, ms) => { timer = setTimeout(() => alive && fn(), ms); };
    const settle = (act) => { setMove((m) => ({ ...m, act: 'rest' })); later(next, restAfter(act, Math.random())); };
    function next() {
      if (document.hidden || holding.current || cueBusy.current) { later(next, 1500); return; }
      const act = pickAct(Math.random(), last.current);
      last.current = act;
      if (act === 'walk') {
        const range = roam(stage.current?.clientWidth ?? 0, body.current?.offsetWidth ?? size);
        const to = walkTarget(Math.random(), xRef.current, range);
        if (to === null) { settle('rest'); return; }
        const plan = walkPlan(xRef.current, to);
        xRef.current = to;
        setMove({ x: to, act: 'walk', dir: plan.dir, ms: plan.ms, steps: plan.steps });
        later(() => settle('walk'), plan.ms);
      } else if (act === 'hop') {
        setMove((m) => ({ ...m, act: 'hop', ms: HOP_MS }));
        later(() => settle('hop'), HOP_MS);
      } else if (act === 'peek') {
        setMove((m) => ({ ...m, act: 'peek', dir: Math.random() < 0.5 ? -1 : 1, ms: PEEK_MS }));
        later(() => settle('peek'), PEEK_MS);
      } else {
        settle('rest');
      }
    }
    later(next, 1800);
    return () => { alive = false; clearTimeout(timer); };
  }, [reduced, size]);

  // เวทีแคบลง (ย่อหน้าต่าง) แล้วมาสคอตยืนเลยขอบ: ดึงกลับมาในระยะที่เดินได้
  useEffect(() => {
    if (!stage.current || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(() => {
      const range = roam(stage.current.clientWidth, body.current?.offsetWidth ?? size);
      if (Math.abs(xRef.current) > range) {
        xRef.current = Math.sign(xRef.current) * range;
        setMove((m) => ({ ...m, x: xRef.current, ms: 300 }));
      }
    });
    ro.observe(stage.current);
    return () => ro.disconnect();
  }, [size]);

  // ปฏิกิริยาต่อฟอร์ม
  useEffect(() => {
    const c = cue ? cueOf(cue.name) : null;
    if (!c) { cueBusy.current = false; setFace(null); return undefined; }
    cueBusy.current = true;
    setFace(c.face);
    if (!reduced) {
      const dir = c.act === 'run' ? (cue.dir ?? towardForm) : towardForm;
      setMove((m) => ({ ...m, act: c.act, dir, ms: c.act === 'run' ? c.ms : m.ms }));
    }
    if (!c.ms) return undefined;     // ค้างไว้จนกว่า cue จะเปลี่ยน (เช่น อยู่ในช่องรหัสผ่าน)
    const h = setTimeout(() => {
      cueBusy.current = false;
      setFace(null);
      setMove((m) => ({ ...m, act: 'rest' }));
    }, c.ms);
    return () => clearTimeout(h);
  }, [cue, reduced, towardForm]);

  // จับเล่นอยู่ (กดค้าง/ลาก) ไม่เดินหนี ปล่อยแล้วรอครู่หนึ่งค่อยเดินต่อ
  useEffect(() => {
    let h;
    const up = () => { clearTimeout(h); h = setTimeout(() => { holding.current = false; }, 1500); };
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    return () => { clearTimeout(h); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up); };
  }, []);

  const style = {
    '--ms-x': `${move.x}px`,
    '--ms-dur': `${move.act === 'walk' ? move.ms : 300}ms`,
    '--ms-dir': move.dir,
    '--ms-step': `${STEP_MS}ms`,
  };
  return (
    <div ref={stage} className="ms-stage" onPointerDown={() => { holding.current = true; }}>
      <div className="ms-walker" style={style} data-bubble={move.x < 0 ? 'right' : 'left'}>
        {children}
        <div ref={body} className={`ms-pose is-${move.act}`} data-dir={move.dir > 0 ? 'right' : 'left'}>
          <Mascot mood="front" size={size} title={title} expression={face ?? undefined} />
        </div>
      </div>
    </div>
  );
}
