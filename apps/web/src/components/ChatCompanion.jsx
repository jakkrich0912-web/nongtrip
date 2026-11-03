import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import Mascot from './Mascot.jsx';
import MascotHead from './MascotHead.jsx';
import ChatMessages from './chat/ChatMessages.jsx';
import { useLanguage } from '../lib/language.jsx';
import { useAuth } from '../lib/auth.jsx';
import { chatSuggestions, useChatSession } from '../lib/useChatSession.js';
import { useCompanionHint } from '../lib/companionContext.jsx';
import { preload, prefersReducedMotion } from '../lib/mascot.js';
import {
  COMPANION_SIZE, DRAG_THRESHOLD, EDGE, GREETING, bodyHeight, clampPos, companionFace, fromRatio, homePos, loadRatio,
  nextActDelay, nextRestDelay, panelPlacement, pickAct, pickWalkTarget, saveRatio, stepToward, toRatio,
  clampRect, loadRect, maximizedRect, moveRect, resizeRect, saveRect,
} from '../lib/companion.js';
import './companion.css';
import '../pages/chat-v2.css';

const viewport = () => ({ w: window.innerWidth, h: window.innerHeight });
const startPos = () => {
  const { w, h } = viewport();
  const saved = loadRatio();
  return saved ? fromRatio(saved, w, h) : homePos(w, h);
};
const GREETED = 'nongtrip-companion-greeted';

// น้องทริปเพื่อนคู่ใจ: เดินไปมาที่ขอบล่างของทุกหน้า ลากไปวางตรงไหนของจอก็ได้ กดแล้วเปิดหน้าต่างแชต
// hidden = อยู่หน้าที่ไม่ต้องแสดง (หน้าแชตเต็ม หน้าเข้าสู่ระบบ) ยังคงสถานะแชตไว้ ไม่ทิ้งบทสนทนา
export default function ChatCompanion({ hidden = false }) {
  const { t, lang } = useLanguage();
  const { user } = useAuth();
  const hint = useCompanionHint();
  const session = useChatSession();
  const { messages, text, setText, busy, context, setContext, send, stop, chooseLodging, input, lastProvince } = session;
  const [rect, setRect] = useState(null); // null = วางติดตัวมาสคอต, มีค่า = ผู้ใช้ลากย้าย/ปรับขนาดเอง
  const [maxed, setMaxed] = useState(null); // ขนาดก่อนขยายเต็ม (null = ไม่ได้ขยายอยู่)
  const [moving, setMoving] = useState(false);
  const panelDrag = useRef(null);

  const [open, setOpen] = useState(false);
  const [vp, setVp] = useState(viewport);
  const [pos, setPos] = useState(startPos); // ใช้คำนวณตำแหน่งหน้าต่างแชต ระหว่างเดินอัปเดตผ่าน ref ไม่ render ซ้ำ
  const [walking, setWalking] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [hover, setHover] = useState(false);
  const [pressed, setPressed] = useState(false);
  const [act, setAct] = useState(null);
  const [react, setReact] = useState(null);
  const [unread, setUnread] = useState(false);
  const [hello, setHello] = useState(false);
  const reduced = prefersReducedMotion();

  useEffect(() => { preload(['base', 'grin'], 'think'); preload(['base', 'grin'], 'wave'); preload(['afraid', 'crying', 'grin', 'star-eyes', 'whistle', 'wink-left', 'smirk', 'tongue', 'squint'], 'front'); }, []);

  const posRef = useRef(pos);
  const rootRef = useRef(null);
  const faceRef = useRef(null);
  const btnRef = useRef(null);
  const scroller = useRef(null);
  const drag = useRef(null);
  const hoverRef = useRef(false);
  const walkingRef = useRef(false);
  const openRef = useRef(false);
  openRef.current = open;

  const apply = useCallback(() => {
    if (rootRef.current) rootRef.current.style.transform = `translate3d(${posRef.current.x}px, ${posRef.current.y}px, 0)`;
  }, []);
  useEffect(apply, [apply, hidden]);

  // ย่อ/ขยายหน้าต่าง: ตัวมาสคอตอยู่ที่เดิมตามสัดส่วนของจอ
  useEffect(() => {
    const onResize = () => {
      const { w, h } = viewport();
      posRef.current = clampPos(posRef.current, w, h);
      setVp({ w, h });
      setPos(posRef.current);
      apply();
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [apply]);

  const remember = () => { const { w, h } = viewport(); saveRatio(toRatio(posRef.current, w, h)); };

  // เดินไปมาตามแนวนอนที่ความสูงเดิม หยุดเมื่อเปิดแชต ลากอยู่ ชี้อยู่ หรือแท็บถูกซ่อน
  useEffect(() => {
    if (hidden || reduced || open) { walkingRef.current = false; setWalking(false); return undefined; }
    let alive = true;
    let raf = 0;
    let timer = 0;
    let target = 0;
    let last = 0;
    let dir = 1;
    const blocked = () => drag.current || hoverRef.current || document.hidden;
    const stopWalk = () => { walkingRef.current = false; setWalking(false); };
    const rest = (ms = nextRestDelay()) => { stopWalk(); timer = window.setTimeout(go, ms); };
    function go() {
      if (!alive) return;
      if (blocked()) { rest(1200); return; }
      target = pickWalkTarget(posRef.current.x, window.innerWidth);
      if (Math.abs(target - posRef.current.x) < 8) { rest(); return; }
      walkingRef.current = true;
      setWalking(true);
      last = 0;
      raf = requestAnimationFrame(tick);
    }
    function tick(ts) {
      if (!alive) return;
      if (blocked()) { rest(1500); return; }
      const dt = last ? Math.min(0.05, (ts - last) / 1000) : 0;
      last = ts;
      const step = stepToward(posRef.current.x, target, dt);
      posRef.current = { ...posRef.current, x: step.x };
      if (step.dir !== dir) { dir = step.dir; if (faceRef.current) faceRef.current.style.transform = `scaleX(${dir < 0 ? -1 : 1})`; }
      apply();
      if (step.arrived) { setPos(posRef.current); remember(); rest(); } else raf = requestAnimationFrame(tick);
    }
    timer = window.setTimeout(go, 1500);
    return () => { alive = false; cancelAnimationFrame(raf); clearTimeout(timer); walkingRef.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hidden, reduced, open, apply]);

  // ท่าเล่นเองตอนยืนพัก (โบกมือ ผิวปาก ขยิบตา …)
  useEffect(() => {
    if (hidden || reduced || open) return undefined;
    let alive = true;
    let timer = 0;
    let clear = 0;
    const schedule = () => {
      timer = window.setTimeout(() => {
        if (!alive) return;
        if (!walkingRef.current && !drag.current && !document.hidden) {
          const next = pickAct();
          setAct(next);
          clear = window.setTimeout(() => setAct(null), next.ms);
        }
        schedule();
      }, nextActDelay());
    };
    schedule();
    return () => { alive = false; clearTimeout(timer); clearTimeout(clear); };
  }, [hidden, reduced, open]);

  // ทักครั้งแรกของแต่ละแท็บ
  useEffect(() => {
    if (hidden) return undefined;
    let seen = false;
    try { seen = sessionStorage.getItem(GREETED) === '1'; } catch { /* ไม่เป็นไร */ }
    if (seen) return undefined;
    const show = window.setTimeout(() => {
      setHello(true);
      try { sessionStorage.setItem(GREETED, '1'); } catch { /* ไม่เป็นไร */ }
    }, 1400);
    const hide = window.setTimeout(() => setHello(false), 6400);
    return () => { clearTimeout(show); clearTimeout(hide); };
  }, [hidden]);

  // อารมณ์ตามผลตอบ: ค้นอยู่ → คิด, เสร็จ → ยิ้ม, ผิดพลาด → ร้องไห้ (ค้างชั่วครู่) และมีจุดแจ้งถ้าหน้าต่างปิดอยู่
  const last = messages[messages.length - 1];
  const status = last?.role === 'bot' ? last.status : null;
  useEffect(() => {
    if (status !== 'done' && status !== 'error') return undefined;
    setReact(status);
    if (!openRef.current) setUnread(true);
    const h = window.setTimeout(() => setReact(null), status === 'error' ? 4200 : 2600);
    return () => clearTimeout(h);
  }, [status, last?.id]);

  // บริบทจากหน้าที่ดูอยู่ (จุดบนแผนที่ สถานที่ จังหวัด)
  const fromHint = useRef(false);
  useEffect(() => {
    if (hint?.lat != null) { setContext({ lat: hint.lat, lon: hint.lon, name: hint.name || '' }); fromHint.current = true; return; }
    if (fromHint.current) { setContext(null); fromHint.current = false; }
    if (hint?.province) lastProvince.current = hint.province;
  }, [hint, setContext, lastProvince]);

  useEffect(() => { if (scroller.current) scroller.current.scrollTop = scroller.current.scrollHeight; }, [messages, open]);

  const openChat = () => {
    setPos(posRef.current);
    const now = viewport();
    setVp(now);
    const saved = loadRect();
    setRect(saved ? clampRect(saved, now.w, now.h) : null);
    setMaxed(null);
    setOpen(true);
    setUnread(false);
    setHello(false);
    window.setTimeout(() => input.current?.focus(), 30);
  };
  const closeChat = () => { setOpen(false); window.setTimeout(() => btnRef.current?.focus(), 0); };
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') closeChat(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open]);

  // กด/ลาก: ขยับเกิน DRAG_THRESHOLD ถือว่าลาก ไม่งั้นถือว่าแตะเพื่อเปิด/ปิดแชต
  const onPointerDown = (e) => {
    if (e.button != null && e.button !== 0) return;
    drag.current = { id: e.pointerId, sx: e.clientX, sy: e.clientY, ox: posRef.current.x, oy: posRef.current.y, moved: false };
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* ไม่เป็นไร */ }
    setPressed(true);
  };
  const onPointerMove = (e) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.sx;
    const dy = e.clientY - d.sy;
    if (!d.moved && Math.hypot(dx, dy) < DRAG_THRESHOLD) return;
    if (!d.moved) { d.moved = true; setDragging(true); setPressed(false); }
    posRef.current = clampPos({ x: d.ox + dx, y: d.oy + dy }, window.innerWidth, window.innerHeight);
    apply();
  };
  const endPointer = (e, cancelled) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    drag.current = null;
    setPressed(false);
    setDragging(false);
    if (d.moved) { setPos(posRef.current); remember(); return; }
    if (!cancelled) { if (open) closeChat(); else openChat(); }
  };
  const onKeyDown = (e) => {
    const step = e.shiftKey ? 96 : 24;
    const move = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
    if (!move) return;
    e.preventDefault();
    posRef.current = clampPos({ x: posRef.current.x + move[0], y: posRef.current.y + move[1] }, window.innerWidth, window.innerHeight);
    setPos(posRef.current);
    apply();
    remember();
  };

  // ลากหัวหน้าต่างเพื่อย้าย / ลากขอบหรือมุมเพื่อปรับขนาด (จอแคบเป็นแผ่นติดล่างจอ ไม่ลาก)
  const currentRect = (p) => ({ left: p.left, top: p.top, width: p.width, height: p.height });
  const startPanel = (mode, dir) => (e) => {
    if (e.button != null && e.button !== 0) return;
    if (mode === 'move' && e.target.closest('button, a')) return;
    const p = panelPlacement(posRef.current, window.innerWidth, window.innerHeight);
    if (p.sheet) return;
    e.preventDefault();
    panelDrag.current = { id: e.pointerId, mode, dir, sx: e.clientX, sy: e.clientY, start: rect ? clampRect(rect, window.innerWidth, window.innerHeight) : currentRect(p) };
    try { e.currentTarget.setPointerCapture(e.pointerId); } catch { /* ไม่เป็นไร */ }
    setMoving(true);
  };
  const movePanel = (e) => {
    const d = panelDrag.current;
    if (!d || d.id !== e.pointerId) return;
    const dx = e.clientX - d.sx;
    const dy = e.clientY - d.sy;
    const next = d.mode === 'move' ? moveRect(d.start, dx, dy, window.innerWidth, window.innerHeight)
      : resizeRect(d.start, d.dir, dx, dy, window.innerWidth, window.innerHeight);
    d.last = next;
    setRect(next);
    if (maxed) setMaxed(null);
  };
  const endPanel = (e) => {
    const d = panelDrag.current;
    if (!d || d.id !== e.pointerId) return;
    panelDrag.current = null;
    setMoving(false);
    if (d.last) saveRect(d.last);
  };
  const toggleMax = () => {
    const { w, h } = viewport();
    if (maxed) { const back = maxed.rect; setRect(back); setMaxed(null); saveRect(back); return; }
    setMaxed({ rect });
    setRect(maximizedRect(w, h));
  };
  const resetPanel = () => { setRect(null); setMaxed(null); saveRect(null); };
  const panelKey = (e) => {
    // Alt+ลูกศร ย้ายหน้าต่าง, Alt+Shift+ลูกศร ปรับขนาด (คีย์บอร์ดใช้แทนการลากได้)
    if (!e.altKey) return;
    const d = { ArrowLeft: [-24, 0], ArrowRight: [24, 0], ArrowUp: [0, -24], ArrowDown: [0, 24] }[e.key];
    if (!d) return;
    const p = panelPlacement(posRef.current, window.innerWidth, window.innerHeight);
    if (p.sheet) return;
    e.preventDefault();
    const start = rect ? clampRect(rect, window.innerWidth, window.innerHeight) : currentRect(p);
    const next = e.shiftKey ? resizeRect(start, 'se', d[0], d[1], window.innerWidth, window.innerHeight)
      : moveRect(start, d[0], d[1], window.innerWidth, window.innerHeight);
    setRect(next);
    setMaxed(null);
    saveRect(next);
  };

  if (hidden) return null;

  const busyStatus = status === 'searching' || status === 'answering' ? status : react;
  const base = companionFace({ open, status: busyStatus, typing: text.length > 0, hover, pressed, dragging });
  const face = base.expression || base.mood !== 'front' ? base : (act ?? base);
  const anchored = open ? panelPlacement(pos, vp.w, vp.h) : null;
  const sheet = anchored?.sheet;
  const place = open && rect && !sheet ? { ...clampRect(rect, vp.w, vp.h), sheet: false, below: false } : anchored;
  const suggestions = chatSuggestions(Boolean(context));
  const fullHref = context ? `/chat?${new URLSearchParams({ lat: context.lat, lon: context.lon, name: context.name || '' })}` : '/chat';
  const side = pos.x > vp.w / 2 ? 'right' : 'left';
  const body = bodyHeight();
  const label = open ? t('ปิดหน้าต่างแชตน้องทริป', 'Close the NongTrip chat') : t('คุยกับน้องทริป', 'Chat with NongTrip');

  return <>
    <div ref={rootRef} className={`nt-comp ${walking ? 'is-walking' : ''} ${dragging ? 'is-dragging' : ''} ${sheet ? 'is-away' : ''}`} style={{ width: COMPANION_SIZE, height: body }}>
      {hello && !open && <p className={`nt-comp-hello nt-comp-hello-${side}`} role="status">{t(GREETING[0], GREETING[1])}</p>}
      <button ref={btnRef} type="button" className="nt-comp-btn" aria-label={label} aria-expanded={open} aria-haspopup="dialog"
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={(e) => endPointer(e, false)} onPointerCancel={(e) => endPointer(e, true)}
        onPointerEnter={(e) => { if (e.pointerType === 'mouse') { hoverRef.current = true; setHover(true); } }}
        onPointerLeave={() => { hoverRef.current = false; setHover(false); }}
        onClick={(e) => { if (e.detail === 0) { if (open) closeChat(); else openChat(); } }} onKeyDown={onKeyDown}>
        <span ref={faceRef} className="nt-comp-face"><span className="nt-comp-sprite"><Mascot size={COMPANION_SIZE} mood={face.mood} expression={face.expression} interactive={false} title="" /></span></span>
        {unread && !open && <span className="nt-comp-dot" aria-hidden="true" />}
      </button>
    </div>
    {open && <section className={`nt-comp-panel ${sheet ? 'is-sheet' : 'is-free'} ${place.below ? 'is-below' : ''} ${moving ? 'is-moving' : ''}`} role="dialog" aria-label={t('แชตกับน้องทริป', 'Chat with NongTrip')}
      style={{ left: place.left, top: place.top, width: place.width, height: place.height }} onKeyDown={panelKey}>
      {!sheet && ['n', 's', 'e', 'w', 'ne', 'nw', 'se', 'sw'].map((dir) => <span key={dir} className={`nt-comp-rs nt-comp-rs-${dir}`} aria-hidden="true"
        onPointerDown={startPanel('resize', dir)} onPointerMove={movePanel} onPointerUp={endPanel} onPointerCancel={endPanel} />)}
      <header className="nt-comp-head" onPointerDown={startPanel('move')} onPointerMove={movePanel} onPointerUp={endPanel} onPointerCancel={endPanel}
        onDoubleClick={(e) => { if (!e.target.closest('button, a')) resetPanel(); }}
        title={sheet ? undefined : t('ลากเพื่อย้าย ดับเบิลคลิกเพื่อกลับไปข้างน้องทริป', 'Drag to move. Double-click to dock back next to NongTrip.')}>
        <MascotHead size={38} />
        <div><strong>{t('น้องทริป', 'NongTrip')}</strong><small>{busy ? t('กำลังค้นให้…', 'Looking for you…') : t('ถามเรื่องที่เที่ยว คาเฟ่ ที่พัก', 'Ask about places, cafés, stays')}</small></div>
        <Link to={fullHref} onClick={closeChat} className="nt-comp-full" aria-label={t('เปิดแชตเต็มหน้า', 'Open full chat page')}>{t('เต็มหน้า', 'Full page')} ↗</Link>
        {!sheet && <button type="button" className="nt-comp-max" onClick={toggleMax} aria-pressed={Boolean(maxed)}
          aria-label={maxed ? t('ย่อหน้าต่างแชต', 'Restore chat size') : t('ขยายหน้าต่างแชต', 'Enlarge chat window')}
          title={maxed ? t('ย่อหน้าต่าง', 'Restore') : t('ขยายหน้าต่าง', 'Enlarge')}>{maxed ? '⤡' : '⤢'}</button>}
        <button type="button" className="nt-comp-close" onClick={closeChat} aria-label={t('ปิด', 'Close')}>×</button>
      </header>
      {context && <div className="nt-chat-context" role="status"><span>{t('ค้นรอบ: ', 'Search around: ')}<strong>{context.name || t('หมุดที่เลือก', 'Selected pin')}</strong></span><button type="button" onClick={() => setContext(null)} disabled={busy}>{t('ล้างจุดค้น', 'Clear location')}</button></div>}
      <div className="nt-comp-scroll" ref={scroller}>
        {lang === 'en' && <p className="nt-chat-privacy">NongTrip currently understands Thai place names best. Replies may be in Thai.</p>}
        <ChatMessages messages={messages} busy={busy} onChooseLodging={chooseLodging} t={t} lang={lang} headSize={30} session={session} />
        {!messages.length && <div className="nt-chat-suggestions" aria-label={t('คำถามแนะนำ', 'Suggested questions')}>{suggestions.map(([thai, english]) => <button key={thai} type="button" disabled={busy} onClick={() => send(t(thai, english))}>{t(thai, english)} <span aria-hidden="true">↗</span></button>)}</div>}
        {!user && messages.length > 0 && <p className="nt-chat-privacy">{t('เข้าสู่ระบบเพื่อเก็บประวัติแชต', 'Sign in to save your chat history.')}</p>}
      </div>
      <form className="nt-chat-composer nt-comp-composer" onSubmit={(event) => { event.preventDefault(); send(text); }}>
        <label className="nt-comp-sr" htmlFor="companion-message">{t('ข้อความถึงน้องทริป', 'Message NongTrip')}</label>
        <div><input ref={input} id="companion-message" value={text} onChange={(event) => setText(event.target.value)} maxLength={500} required placeholder={t('บอกชื่อที่พัก หรือพิมพ์คำถามได้เลย…', 'Your accommodation or question…')} autoComplete="off" />{busy && <button type="button" className="nt-chat-stop" onClick={stop}>{t('หยุด', 'Stop')}</button>}<button type="submit" disabled={busy || !text.trim()}>{t('ส่ง', 'Send')} <span aria-hidden="true">↑</span></button></div>
      </form>
    </section>}
  </>;
}
