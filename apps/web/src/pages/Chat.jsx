import { useEffect, useRef, useState } from 'react';
import Mascot from '../components/Mascot.jsx';
import MascotHead from '../components/MascotHead.jsx';
import { useAuth } from '../lib/auth.jsx';
import { licenseLabel, numberCitations, safeUrl, sendChat } from '../lib/chat.js';

const SUGGEST = ['คาเฟ่ในเชียงใหม่', 'ที่เที่ยวในน่าน 5 แห่ง', 'ที่เที่ยวใกล้ที่พักใน 10 กม.'];
const HELLO = { role: 'bot', lines: ['สวัสดีค่ะ บอกชื่อที่พัก ชื่อจังหวัด หรือถามเรื่องที่เที่ยวรอบๆ ได้เลย'] };

// หน้าแชต (CONTRACT ข้อ 3.2) รายชื่อ ระยะ และที่มา OSM อยู่ในบรรทัดคำตอบแล้ว จึงไม่แสดงซ้ำเป็นการ์ด
// ข้อความทุกบรรทัดและชื่อสถานที่แสดงเป็นข้อความธรรมดา ไม่ใส่เป็น HTML
export default function Chat() {
  const { user } = useAuth();
  const [msgs, setMsgs] = useState([HELLO]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [context, setContext] = useState(null); // { lat, lon, name } ที่พักที่ผู้ใช้เลือกจากคำตอบ
  const chatId = useRef(null);
  const abort = useRef(null);
  const end = useRef(null);

  useEffect(() => () => abort.current?.abort(), []);
  useEffect(() => { chatId.current = null; }, [user]);
  useEffect(() => { end.current?.scrollIntoView?.({ block: 'end', behavior: 'smooth' }); }, [msgs]);

  // แก้ข้อความบอทตัวล่าสุด
  const patch = (fn) => setMsgs((m) => {
    const copy = m.slice();
    copy[copy.length - 1] = fn(copy[copy.length - 1]);
    return copy;
  });

  const send = async (raw, ctx = context) => {
    const t = raw.trim();
    if (!t || busy) return;
    setText('');
    setBusy(true);
    setMsgs((m) => [...m, { role: 'user', lines: [t] }, { role: 'bot', lines: [], lodgings: null, sources: [], working: true }]);
    const ctrl = new AbortController();
    abort.current = ctrl;
    try {
      await sendChat({ message: t, context: ctx && { lat: ctx.lat, lon: ctx.lon }, chat_id: user ? chatId.current : null },
        (ev, data) => {
          if (ev === 'lodgings') patch((b) => ({ ...b, lodgings: data }));
          else if (ev === 'sources') patch((b) => ({ ...b, sources: data.items ?? [] }));
          else if (ev === 'token') patch((b) => ({ ...b, lines: [...b.lines, data.text.replace(/\n$/, '')] }));
          else if (ev === 'done' && user && data.chat_id) chatId.current = data.chat_id;
        }, ctrl.signal);
      patch((b) => ({ ...b, working: false }));
    } catch (e) {
      if (e?.name === 'AbortError') return;
      if (e?.status === 404) chatId.current = null; // แชตเดิมถูกลบไปแล้ว รอบหน้าเริ่มแชตใหม่
      patch((b) => ({ ...b, working: false, error: e?.message ?? 'ระบบขัดข้องชั่วคราว ลองใหม่อีกครั้ง' }));
    } finally {
      if (abort.current === ctrl) abort.current = null;
      setBusy(false);
    }
  };

  // เลือกที่พักจากคำตอบ แล้วค้นรอบที่พักนั้นต่อ
  const pick = (l) => {
    const ctx = { lat: l.lat, lon: l.lon, name: l.name };
    setContext(ctx);
    send('ที่เที่ยวใกล้ที่พัก', ctx);
  };

  return (
    <section className="chat">
      <div className="chat-head">
        <Mascot size={72} mood="happy" />
        <div>
          <h2>ถามน้องทริป</h2>
          <p className="note">ผู้ช่วยค้นจากข้อมูลจริงชุดเดียวกับหน้าค้นหา ไม่เดาข้อมูล</p>
        </div>
      </div>

      <div className="msgs" aria-live="polite">
        {msgs.map((m, i) => (
          <div key={i} className={`row ${m.role}`}>
            {m.role === 'bot' && <MascotHead size={38} className="avatar" />}
            <div className={`msg ${m.role}`}>
              {m.working && !m.lines.length && <p className="ln typing">กำลังค้น…</p>}
              {m.lines.map((ln, j) => <p key={j} className="ln">{numberCitations(ln, m.sources)}</p>)}
              {m.error && <p className="ln err" role="alert">{m.error}</p>}
              {m.lodgings?.items?.length > 1 && (
                <div className="chat-picks">
                  {m.lodgings.items.slice(0, 6).map((l, j) => (
                    <button key={l.id ?? j} className="chip" disabled={busy} onClick={() => pick(l)}>{l.name}</button>
                  ))}
                </div>
              )}
              {m.sources?.length > 0 && (
                <div className="chat-sources">
                  <p className="src-h">ที่มา</p>
                  <ol>
                    {m.sources.map((s) => (
                      <li key={s.id}>
                        {safeUrl(s.url) ? <a href={safeUrl(s.url)} target="_blank" rel="noreferrer noopener">{s.title}</a> : s.title}
                        {licenseLabel(s) && <small> ({licenseLabel(s)})</small>}
                      </li>
                    ))}
                  </ol>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>

      {context && (
        <p className="note chat-ctx">
          ค้นรอบ {context.name}{' '}
          <button type="button" className="linkish" onClick={() => setContext(null)}>ล้าง</button>
        </p>
      )}
      <div className="suggest">
        {SUGGEST.map((s) => <button key={s} className="chip" disabled={busy} onClick={() => send(s)}>{s}</button>)}
      </div>
      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text); }}>
        <input value={text} maxLength={500} onChange={(e) => setText(e.target.value)} placeholder="พิมพ์คำถาม" aria-label="ข้อความ" />
        <button className="btn" disabled={busy || !text.trim()}>{busy ? 'รอสักครู่' : 'ส่ง'}</button>
      </form>
    </section>
  );
}
