import { useEffect, useRef, useState } from 'react';
import Mascot from './Mascot.jsx';
import MotionSprite from './MotionSprite.jsx';
import { loadMotion, walkFps } from '../lib/mascotFrames.js';
import { prefersReducedMotion } from '../lib/mascot.js';
import './mascotStage.css';
import { HOP_MS, LOOK_MS, PEEK_MS, STEP_MS, TAIL_MS, cueOf, pickAct, restAfter, roam, walkPlan, walkTarget } from '../lib/mascotMotion.js';

// เวทีของน้องทริป: ใช้มาสคอตตัวเดิม (มองตามเคอร์เซอร์ จับดึงเล่นได้เหมือนเดิม) แล้วเพิ่มท่าทางเอง
// เดินไปมา กระโดดดึ๋ง มองซ้ายขวา กระดิกหาง ชะโงกดู ยืนหายใจ และตอบสนองฟอร์ม (cue) เช่น ปิดตาตอนพิมพ์รหัสผ่าน
// เดิน/วิ่ง/กระโดด/มองรอบ/กระดิกหาง เล่นภาพทีละเฟรม (MotionSprite) แทนมาสคอตนิ่งทั้งภาพ ไม่ซ้อนกัน
// ระหว่างผู้ใช้จับเล่น หรือมีสีหน้าจากฟอร์ม ใช้มาสคอตนิ่งเดิมเสมอ (สีหน้า gaze และการลากไม่ถูกภาพเคลื่อนไหวแย่ง)
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
  const [move, setMoveRaw] = useState({ x: 0, act: 'rest', dir: 1, ms: 0, steps: 0, n: 0 });
  // n เพิ่มทุกครั้งที่เปลี่ยนท่าหรือที่ยืน ใช้บอกว่าภาพเคลื่อนไหวของท่านี้เล่นครบรอบแล้วหรือยัง
  const setMove = (fn) => setMoveRaw((m) => {
    const next = typeof fn === 'function' ? fn(m) : fn;
    return next.act !== m.act || next.x !== m.x ? { ...next, n: (m.n ?? 0) + 1 } : { ...next, n: m.n };
  });
  const [face, setFace] = useState(null);
  const [held, setHeld] = useState(false);
  const [loaded, setLoaded] = useState({});      // ชุดภาพเคลื่อนไหวที่โหลดครบแล้ว
  const [spriteDone, setSpriteDone] = useState(-1); // seq ของท่าที่ภาพเล่นครบรอบแล้ว (กลับไปภาพนิ่ง)
  const reduced = useRef(prefersReducedMotion()).current;
  const towardForm = formSide === 'right' ? 1 : -1;

  // โหลดภาพเคลื่อนไหวล่วงหน้า ชุดไหนยังโหลดไม่ครบใช้ท่าแบบเดิม (CSS) ไปก่อน
  useEffect(() => {
    if (reduced) return undefined;
    let alive = true;
    for (const name of ['walk', 'hop', 'look-around', 'tail-wag']) {
      loadMotion(name).then((ok) => { if (alive && ok) setLoaded((l) => ({ ...l, [name]: true })); });
    }
    return () => { alive = false; };
  }, [reduced]);

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
        const dist = Math.abs(to - xRef.current);
        xRef.current = to;
        setMove({ x: to, act: 'walk', dir: plan.dir, ms: plan.ms, steps: plan.steps, dist });
        later(() => settle('walk'), plan.ms);
      } else if (act === 'hop') {
        setMove((m) => ({ ...m, act: 'hop', ms: HOP_MS }));
        later(() => settle('hop'), HOP_MS);
      } else if (act === 'look' || act === 'tail') {
        const ms = act === 'look' ? LOOK_MS : TAIL_MS;
        setMove((m) => ({ ...m, act, dir: 1, ms }));
        later(() => settle(act), ms);
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
    const up = () => { clearTimeout(h); h = setTimeout(() => { holding.current = false; setHeld(false); }, 1500); };
    window.addEventListener('pointerup', up);
    window.addEventListener('pointercancel', up);
    return () => { clearTimeout(h); window.removeEventListener('pointerup', up); window.removeEventListener('pointercancel', up); };
  }, []);

  // ท่าที่มีภาพทีละเฟรม: ใช้เมื่อโหลดครบ ไม่ได้ถูกจับอยู่ ไม่มีสีหน้าจากฟอร์ม และยังเล่นไม่ครบรอบ
  const motionOf = { walk: 'walk', run: 'walk', hop: 'hop', look: 'look-around', tail: 'tail-wag' };
  const want = motionOf[move.act];
  const sprite = !reduced && !held && want && loaded[want] && spriteDone !== move.n && (!face || move.act === 'hop' || move.act === 'run') ? want : null;
  const doneNow = () => setSpriteDone(move.n);
  const spriteFps = move.act === 'walk' && move.ms ? walkFps(Math.abs(move.dist ?? 0) / (move.ms / 1000), size)
    : move.act === 'run' ? 14 : undefined;
  const spriteLoops = move.act === 'hop' || move.act === 'look' ? 1 : move.act === 'tail' ? 2 : Infinity;

  const style = {
    '--ms-x': `${move.x}px`,
    '--ms-dur': `${move.act === 'walk' ? move.ms : 300}ms`,
    '--ms-dir': move.dir,
    '--ms-step': `${STEP_MS}ms`,
  };
  return (
    <div ref={stage} className="ms-stage" onPointerDown={() => { holding.current = true; setHeld(true); }}>
      <div className={`ms-walker${sprite === 'walk' && move.act === 'walk' ? ' is-stepping' : ''}`} style={style} data-bubble={move.x < 0 ? 'right' : 'left'}>
        {children}
        <div ref={body} className={`ms-pose is-${move.act}${sprite ? ' has-sprite' : ''}`} data-dir={move.dir > 0 ? 'right' : 'left'}>
          <div className="ms-still" style={sprite ? { visibility: 'hidden' } : undefined}>
            <Mascot mood="front" size={size} title={title} expression={face ?? undefined} />
          </div>
          {sprite && <MotionSprite key={move.n} name={sprite} size={size} dir={move.dir}
            fps={spriteFps} loops={spriteLoops} onEnd={doneNow} />}
        </div>
      </div>
    </div>
  );
}
