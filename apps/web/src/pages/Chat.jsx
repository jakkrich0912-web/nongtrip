import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import ChatMessages from '../components/chat/ChatMessages.jsx';
import { useLanguage } from '../lib/language.jsx';
import { useAuth } from '../lib/auth.jsx';
import { deleteChat, myChats, renameChat } from '../lib/api.js';
import { groupChats } from '../lib/chatHistory.js';
import { chatSuggestions, useChatSession } from '../lib/useChatSession.js';
import './chat-v2.css';
import './chat-gpt.css';

const MAX = 500;

// หน้าแชตเต็มจอแบบแอปแชตทั่วไป: แถบประวัติด้านซ้าย บทสนทนาตรงกลาง ช่องพิมพ์ติดล่าง
export default function Chat() {
  const { lang, t } = useLanguage();
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const [initial] = useState(() => {
    const lat = Number.parseFloat(params.get('lat'));
    const lon = Number.parseFloat(params.get('lon'));
    return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon, name: params.get('name') || '' } : null;
  });
  const session = useChatSession({ initialContext: initial });
  const { messages, text, setText, busy, context, setContext, send, stop, chooseLodging, input, newChat, openChat, currentChat } = session;
  const [history, setHistory] = useState({ status: 'idle', items: [] });
  const [sideOpen, setSideOpen] = useState(false);
  const [openError, setOpenError] = useState('');
  const [renaming, setRenaming] = useState(null);     // { id, title } ที่กำลังเปลี่ยนชื่อ
  const [confirmDel, setConfirmDel] = useState(null); // รหัสแชตที่รอกดยืนยันลบ
  const [atBottom, setAtBottom] = useState(true);
  const scroller = useRef(null);
  const stick = useRef(true); // อยู่ล่างสุดอยู่แล้วจึงเลื่อนตามข้อความใหม่ ถ้าผู้ใช้เลื่อนขึ้นไปอ่าน ไม่ดึงกลับ

  const loadHistory = useCallback(() => {
    if (!user) { setHistory({ status: 'idle', items: [] }); return; }
    setHistory((h) => ({ ...h, status: 'loading' }));
    myChats().then((d) => setHistory({ status: 'ok', items: d.items ?? [] })).catch(() => setHistory({ status: 'error', items: [] }));
  }, [user]);
  useEffect(loadHistory, [loadHistory]);
  // ตอบเสร็จแล้วแชตใหม่ถูกบันทึก: รีเฟรชรายการประวัติ
  const lastStatus = messages[messages.length - 1]?.status;
  useEffect(() => { if (user && lastStatus === 'done') loadHistory(); }, [user, lastStatus, loadHistory]);

  const open = async (id) => {
    setOpenError('');
    setSideOpen(false);
    stick.current = true;
    try {
      await openChat(id);
    } catch {
      setOpenError(t('เปิดแชตนี้ไม่ได้ อาจถูกลบไปแล้ว', 'Could not open this chat. It may have been deleted.'));
    }
  };
  // เปิดจากลิงก์ในหน้าทริปของฉัน (/chat?chat=12)
  const wanted = params.get('chat');
  useEffect(() => {
    if (!user || !wanted) return;
    open(wanted);
    const next = new URLSearchParams(params);
    next.delete('chat');
    setParams(next, { replace: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, wanted]);

  const fresh = () => { setOpenError(''); newChat(); setSideOpen(false); };

  const saveTitle = async () => {
    const r = renaming;
    setRenaming(null);
    const title = r?.title.trim();
    if (!r || !title) return;
    setHistory((h) => ({ ...h, items: h.items.map((c) => c.id === r.id ? { ...c, title } : c) }));
    try { await renameChat(r.id, title); } catch { loadHistory(); }
  };
  const remove = async (id) => {
    setConfirmDel(null);
    setHistory((h) => ({ ...h, items: h.items.filter((c) => c.id !== id) }));
    if (id === currentChat) newChat();
    try { await deleteChat(id); } catch { loadHistory(); }
  };

  // ช่องพิมพ์ขยายตามข้อความ (สูงสุดราว 8 บรรทัด)
  useLayoutEffect(() => {
    const el = input.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 220)}px`;
  }, [text, input]);
  useEffect(() => {
    const el = scroller.current;
    if (!el) return;
    if (stick.current) el.scrollTop = el.scrollHeight;
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80);
  }, [messages]);
  const onScroll = () => {
    const el = scroller.current;
    if (!el) return;
    stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
    setAtBottom(stick.current);
  };
  const toBottom = () => {
    const el = scroller.current;
    if (!el) return;
    stick.current = true;
    setAtBottom(true);
    el.scrollTo({ top: el.scrollHeight, behavior: window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
  };
  const submit = (value) => { stick.current = true; send(value); };
  const onKeyDown = (event) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      if (!busy && text.trim()) submit(text);
    }
  };
  const suggestions = chatSuggestions(Boolean(context));
  const empty = messages.length === 0;
  const mapHref = context ? `/search?${new URLSearchParams({ lat: context.lat, lon: context.lon, name: context.name || '' })}` : '/search';

  return <div className={`ntg ${sideOpen ? 'is-side-open' : ''}`}>
    <aside className="ntg-side" id="ntg-side" aria-label={t('ประวัติแชต', 'Chat history')}>
      <button type="button" className="ntg-new" onClick={fresh}><span aria-hidden="true">＋</span> {t('แชตใหม่', 'New chat')}</button>
      <Link className="ntg-side-link" to={mapHref}><span aria-hidden="true">⌖</span> {t('เปิดแผนที่ค้นรอบที่พัก', 'Open the map')}</Link>
      <h2 className="ntg-side-title">{t('แชตก่อนหน้า', 'Previous chats')}</h2>
      {!user && <p className="ntg-side-note"><Link to="/login">{t('เข้าสู่ระบบ', 'Log in')}</Link> {t('เพื่อเก็บและเปิดแชตเก่าได้', 'to save and reopen your chats.')}</p>}
      {user && history.status === 'loading' && history.items.length === 0 && <p className="ntg-side-note">{t('กำลังโหลด…', 'Loading…')}</p>}
      {user && history.status === 'error' && <p className="ntg-side-note">{t('โหลดประวัติไม่ได้', 'Could not load history.')}</p>}
      {user && history.status === 'ok' && history.items.length === 0 && <p className="ntg-side-note">{t('ยังไม่มีแชต เริ่มถามได้เลย', 'No chats yet. Ask away!')}</p>}
      {user && groupChats(history.items).map((g) => <div key={g.key} className="ntg-group">
        <h3 className="ntg-group-title">{t(g.th, g.en)}</h3>
        <ul className="ntg-history">
          {g.items.map((c) => <li key={c.id} className={confirmDel === c.id ? 'is-confirm' : ''}>
            {renaming?.id === c.id
              ? <input className="ntg-rename" aria-label={t('ชื่อแชตใหม่', 'New chat name')} value={renaming.title} maxLength={80} autoFocus
                  onChange={(e) => setRenaming({ ...renaming, title: e.target.value })} onBlur={saveTitle}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveTitle(); } if (e.key === 'Escape') setRenaming(null); }} />
              : confirmDel === c.id
                ? <div className="ntg-confirm" role="group" aria-label={t('ยืนยันการลบ', 'Confirm delete')}>
                    <span>{t('ลบแชตนี้?', 'Delete this chat?')}</span>
                    <button type="button" className="ntg-yes" onClick={() => remove(c.id)}>{t('ลบ', 'Delete')}</button>
                    <button type="button" onClick={() => setConfirmDel(null)}>{t('ไม่', 'No')}</button>
                  </div>
                : <>
                    <button type="button" className="ntg-open" aria-current={c.id === currentChat ? 'true' : undefined} onClick={() => open(c.id)} disabled={busy} title={c.title}>{c.title}</button>
                    <span className="ntg-item-tools">
                      <button type="button" onClick={() => setRenaming({ id: c.id, title: c.title })} aria-label={t(`เปลี่ยนชื่อแชต ${c.title}`, `Rename chat ${c.title}`)} title={t('เปลี่ยนชื่อ', 'Rename')}>✎</button>
                      <button type="button" onClick={() => setConfirmDel(c.id)} disabled={busy && c.id === currentChat} aria-label={t(`ลบแชต ${c.title}`, `Delete chat ${c.title}`)} title={t('ลบ', 'Delete')}>🗑</button>
                    </span>
                  </>}
          </li>)}
        </ul>
      </div>)}
      {user && <Link className="ntg-side-manage" to="/me">{t('จัดการ/ลบประวัติในทริปของฉัน', 'Manage or delete in My trips')}</Link>}
    </aside>
    <button type="button" className="ntg-scrim" aria-label={t('ปิดแถบประวัติ', 'Close history')} tabIndex={sideOpen ? 0 : -1} onClick={() => setSideOpen(false)} />

    <section className="ntg-main" aria-labelledby="chat-title">
      <div className="ntg-top">
        <button type="button" className="ntg-menu" aria-label={t('เปิดแถบประวัติ', 'Open history')} aria-expanded={sideOpen} aria-controls="ntg-side" onClick={() => setSideOpen(true)}>☰</button>
        <h1 id="chat-title">{t('คุยกับน้องทริป', 'Chat with NongTrip')}</h1>
        <button type="button" className="ntg-top-new" onClick={fresh} aria-label={t('แชตใหม่', 'New chat')} title={t('แชตใหม่', 'New chat')}>＋</button>
      </div>

      <div className="ntg-scroll" ref={scroller} onScroll={onScroll}>
        <div className="ntg-col">
          {openError && <p className="nt-chat-error ntg-banner" role="alert">{openError}</p>}
          {empty ? <div className="ntg-empty">
            <Mascot size={110} mood="front" />
            <h2>{t('วันนี้ให้น้องทริปช่วยอะไรดี?', 'How can NongTrip help today?')}</h2>
            <p>{t('บอกชื่อที่พักหรือจังหวัด แล้วน้องทริปหาที่เที่ยวกับคาเฟ่รอบ ๆ ให้ หรือจะถามเรื่องอื่นก็ได้', 'Tell me your stay or province and I’ll find attractions and cafés nearby, or ask me anything.')}</p>
            <div className="ntg-suggest" aria-label={t('คำถามแนะนำ', 'Suggested questions')}>
              {suggestions.map(([thai, english]) => <button key={thai} type="button" disabled={busy} onClick={() => submit(t(thai, english))}>{t(thai, english)}</button>)}
            </div>
          </div> : <ChatMessages messages={messages} busy={busy} onChooseLodging={chooseLodging} t={t} lang={lang} session={session} greeting={false} headSize={32} actions />}
        </div>
      </div>

      <div className="ntg-bottom">
        {!empty && !atBottom && <button type="button" className="ntg-down" onClick={toBottom} aria-label={t('เลื่อนลงล่างสุด', 'Scroll to latest')} title={t('ข้อความล่าสุด', 'Latest')}>↓</button>}
        <div className="ntg-col">
          {context && <div className="ntg-context" role="status"><span>{t('ค้นรอบ: ', 'Searching around: ')}<strong>{context.name || t('หมุดที่เลือก', 'Selected pin')}</strong></span><button type="button" onClick={() => setContext(null)} disabled={busy} aria-label={t('ล้างจุดค้น', 'Clear location')}>×</button></div>}
          <form className="ntg-composer" onSubmit={(event) => { event.preventDefault(); if (!busy) submit(text); }}>
            <label className="ntg-sr" htmlFor="chat-message">{t('ข้อความถึงน้องทริป', 'Message NongTrip')}</label>
            <textarea ref={input} id="chat-message" rows={1} value={text} onChange={(event) => setText(event.target.value)} onKeyDown={onKeyDown}
              maxLength={MAX} required placeholder={t('ถามน้องทริปได้เลย…', 'Ask NongTrip anything…')} autoComplete="off" />
            {busy
              ? <button type="button" className="ntg-send ntg-stop" onClick={stop} aria-label={t('หยุด', 'Stop')} title={t('หยุด', 'Stop')}><span aria-hidden="true">■</span></button>
              : <button type="submit" className="ntg-send" disabled={!text.trim()} aria-label={t('ส่งข้อความ', 'Send')} title={t('ส่งข้อความ', 'Send')}><span aria-hidden="true">↑</span></button>}
          </form>
          <p className="ntg-foot">
            {text.length >= 400 && <span className="nt-chat-count">{text.length}/{MAX} · </span>}
            {t('น้องทริปอาจผิดพลาดได้ ระยะทางเป็นเส้นตรง ไม่ใช่ระยะขับรถ', 'NongTrip can make mistakes. Distances are straight-line, not driving.')}
            {!user && <> · <Link to="/login">{t('เข้าสู่ระบบเพื่อเก็บประวัติ', 'Log in to save history')}</Link></>}
            {lang === 'en' && <> · {t('', 'Thai place names work best.')}</>}
          </p>
        </div>
      </div>
    </section>
  </div>;
}
