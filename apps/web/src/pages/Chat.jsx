import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import ChatMessages from '../components/chat/ChatMessages.jsx';
import { useLanguage } from '../lib/language.jsx';
import { useAuth } from '../lib/auth.jsx';
import { chatSuggestions, useChatSession } from '../lib/useChatSession.js';
import './chat-v2.css';

export default function Chat() {
  const { lang, t } = useLanguage();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [initial] = useState(() => {
    const lat = Number.parseFloat(params.get('lat'));
    const lon = Number.parseFloat(params.get('lon'));
    return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon, name: params.get('name') || '' } : null;
  });
  const { messages, text, setText, busy, context, setContext, send, stop, chooseLodging, input } = useChatSession({ initialContext: initial });
  const suggestions = chatSuggestions(Boolean(context));
  return <section className="nt-chat" aria-labelledby="chat-title">
    <header className="nt-chat-header">
      <Mascot size={76} mood="front" expression={messages[messages.length - 1]?.status === 'error' ? 'crying' : undefined} />
      <div><p className="nt-chat-eyebrow">YOUR LITTLE TRAVEL COMPANION</p><h1 id="chat-title">{t('คุยกับน้องทริป', 'Chat with NongTrip')}</h1><p>{t('เริ่มจากชื่อที่พักหรือจังหวัด แล้วค่อย ๆ หาที่ที่อยากไป', 'Start with your accommodation or province. Let’s find your next stop.')}</p></div>
      <Link to={context ? `/search?${new URLSearchParams({ lat: context.lat, lon: context.lon, name: context.name || '' })}` : '/search'} className="nt-chat-map-link">{t('เปิดแผนที่', 'Open map')} ↗</Link>
    </header>
    <div className="nt-chat-body">
      <p className="nt-chat-privacy">{t('แต่ละคำถามค้นใหม่จากจังหวัดหรือจุดที่เลือกไว้', 'Each question searches again from the province or your selected location.')} {!user && t('เข้าสู่ระบบเพื่อเก็บประวัติแชต', 'Sign in to save your chat history.')}</p>
      {lang === 'en' && <p className="nt-chat-privacy">NongTrip currently understands Thai place names best. Replies may be in Thai.</p>}
      {context && <div className="nt-chat-context" role="status"><span>{t('ค้นรอบ: ', 'Search around: ')}<strong>{context.name || t('หมุดที่เลือก', 'Selected pin')}</strong></span><button type="button" onClick={() => setContext(null)} disabled={busy}>{t('ล้างจุดค้น', 'Clear location')}</button></div>}
      <ChatMessages messages={messages} busy={busy} onChooseLodging={chooseLodging} t={t} lang={lang} />
      <div className="nt-chat-suggestions" aria-label={t('คำถามแนะนำ', 'Suggested questions')}>{suggestions.map(([thai, english]) => <button key={thai} type="button" disabled={busy} onClick={() => send(t(thai, english))}>{t(thai, english)} <span aria-hidden="true">↗</span></button>)}</div>
      <form className="nt-chat-composer" onSubmit={(event) => { event.preventDefault(); send(text); }}>
        <label className="nt-chat-input-label" htmlFor="chat-message">{t('ข้อความถึงน้องทริป', 'Message NongTrip')}{text.length >= 400 && <small className="nt-chat-count"> · {text.length}/500</small>}</label>
        <div><input ref={input} id="chat-message" value={text} onChange={(event) => setText(event.target.value)} maxLength={500} required placeholder={t('บอกชื่อที่พัก หรือพิมพ์คำถามได้เลย…', 'Your accommodation or question…')} autoComplete="off" />{busy && <button type="button" className="nt-chat-stop" onClick={stop}>{t('หยุด', 'Stop')}</button>}<button type="submit" disabled={busy || !text.trim()}>{busy ? t('กำลังตอบ…', 'Replying…') : t('ส่งข้อความ', 'Send')} <span aria-hidden="true">↑</span></button></div>
      </form>
    </div>
  </section>;
}
