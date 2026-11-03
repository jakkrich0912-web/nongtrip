import { useEffect, useRef, useState } from 'react';
import { noticeText } from '../lib/notices.js';
import { Link, useSearchParams } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import MascotHead from '../components/MascotHead.jsx';
import SourceCards from '../components/chat/SourceCards.jsx';
import { useLanguage } from '../lib/language.jsx';
import { useAuth } from '../lib/auth.jsx';
import { numberCitations, safeUrl as safeSourceUrl, sendChat } from '../lib/chat.js';
import './chat-v2.css';

function ResultCards({ result, t, lang }) {
  if (!result) return null;
  const valid = result.validation?.ok !== false;
  return <div className="nt-chat-results">
    {!valid && <p className="nt-chat-error" role="alert">{t('ผลค้นยังไม่ผ่านการตรวจสอบ จึงยังไม่แสดงสถานที่', 'These results could not be verified, so places are hidden.')}</p>}
    {(result.notices ?? []).map((notice, index) => <p className="nt-chat-notice" key={index}>{noticeText(notice, lang)}</p>)}
    {valid && (result.items ?? []).map((place) => {
      const source = safeSourceUrl(place.source_url);
      const maps = safeSourceUrl(place.maps_url);
      const directions = safeSourceUrl(place.directions_url);
      return <article className="nt-chat-place" key={place.id}>
        <div><strong>{lang === 'en' ? place.name_en || place.name_th : place.name_th}</strong>
          <small>{place.kind === 'cafe' ? t('คาเฟ่', 'Café') : t('สถานที่ท่องเที่ยว', 'Attraction')} · {place.source === 'verified' ? t('ตรวจชื่อและพิกัดแล้ว', 'Name and coordinates checked') : 'OpenStreetMap'}</small>
        </div>
        {typeof place.distance_km === 'number' && <span className="nt-chat-distance">{place.distance_km} {t('กม. เส้นตรง', 'km straight-line')}</span>}
        <div className="nt-chat-place-links">
          {source && <a href={source} target="_blank" rel="noreferrer">{t('แหล่งที่มา', 'Source')} ↗</a>}
          {maps && <a href={maps} target="_blank" rel="noreferrer">{t('ดูบนแผนที่', 'View map')} ↗</a>}
          {directions && <a href={directions} target="_blank" rel="noreferrer">{t('นำทางด้วย Google Maps', 'Directions with Google Maps')} ↗</a>}
        </div>
      </article>;
    })}
    <p className="nt-chat-footnote">{t('ระยะทางเป็นเส้นตรงจากจุดค้น ไม่ใช่ระยะขับรถ', 'Distances are straight-line from the search point, not driving distances.')}</p>
    <p className="nt-chat-footnote">Map data © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors (ODbL)</a></p>
  </div>;
}

export default function Chat() {
  const { lang, t } = useLanguage();
  const { user } = useAuth();
  const [params] = useSearchParams();
  const [context, setContext] = useState(() => {
    const lat = Number.parseFloat(params.get('lat'));
    const lon = Number.parseFloat(params.get('lon'));
    return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon, name: params.get('name') || '' } : null;
  });
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const controller = useRef(null);
  const chatId = useRef(null);
  const lastProvince = useRef(null); // จังหวัดที่ถามไว้ล่าสุด (จาก event done)
  const serial = useRef(0);
  const activeId = useRef(null);
  const input = useRef(null);
  useEffect(() => () => controller.current?.abort(), []);
  useEffect(() => { chatId.current = null; }, [user?.id]);

  const send = async (value, displayText = value) => {
    const message = value.trim();
    if (!message || message.length > 500 || controller.current) return;
    const id = ++serial.current;
    const aborter = new AbortController();
    controller.current = aborter;
    activeId.current = id;
    setBusy(true);
    setText('');
    setMessages((items) => [...items, { id: `user-${id}`, role: 'user', text: displayText.trim() }, { id, role: 'bot', text: '', sources: [], status: 'searching' }]);
    const update = (patch) => setMessages((items) => items.map((item) => item.id === id ? (typeof patch === 'function' ? patch(item) : { ...item, ...patch }) : item));
    try {
      await sendChat({ message, context: context && { lat: context.lat, lon: context.lon }, chat_id: user ? chatId.current : null, last_province: lastProvince.current, lang }, (event, data) => {
        if (aborter.signal.aborted) return;
        if (event === 'token' && typeof data.text === 'string') update((item) => ({ ...item, text: item.text + data.text, status: 'answering' }));
        if (event === 'places') update({ places: data });
        if (event === 'lodgings') update({ lodgings: data });
        if (event === 'sources') update({ sources: Array.isArray(data.items) ? data.items : [] });
        if (event === 'done') {
          if (user && data.chat_id) chatId.current = data.chat_id;
          if (typeof data.province === 'string') lastProvince.current = data.province;
          update({ status: 'done', mode: data.mode });
        }
      }, aborter.signal);
    } catch (error) {
      if (error?.status === 404) chatId.current = null; // แชตเดิมถูกลบไปแล้ว รอบหน้าเริ่มแชตใหม่
      if (!aborter.signal.aborted) update({ status: 'error', error: error.message });
    } finally {
      if (controller.current === aborter) {
        controller.current = null;
        setBusy(false);
      }
    }
  };
  // หยุดรอคำตอบ: ยกเลิกคำขอที่ค้างอยู่ ข้อความที่ได้มาแล้วยังคงอยู่ และให้ถามใหม่ได้ทันที
  const stop = () => {
    const aborter = controller.current;
    if (!aborter) return;
    aborter.abort();
    controller.current = null;
    setBusy(false);
    setMessages((items) => items.map((item) => item.id === activeId.current ? { ...item, status: 'stopped' } : item));
    input.current?.focus();
  };
  const chooseLodging = (lodging) => {
    setContext({ lat: lodging.lat, lon: lodging.lon, name: lodging.name });
    input.current?.focus();
  };
  // Suggested questions are sent in the selected language; the chat parser understands both Thai and English.
  const suggestions = context ? [
    ['คาเฟ่ใกล้ที่พักมีที่ไหนบ้าง', 'Which cafés are near my accommodation?'],
    ['ที่เที่ยวในระยะเส้นตรง 10 กม.', 'Attractions within 10 km straight-line distance'],
    ['ที่เที่ยวรอบที่พัก', 'Attractions near my accommodation'],
  ] : [
    ['คาเฟ่ในเชียงใหม่', 'Cafés in Chiang Mai'],
    ['ที่เที่ยวในเชียงราย ในระยะเส้นตรง 10 กม.', 'Attractions in Chiang Rai within 10 km straight-line distance'],
    ['ที่เที่ยวในกรุงเทพมหานคร', 'Attractions in Bangkok'],
  ];
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
      <div className="nt-chat-messages" role="log" aria-label={t('บทสนทนา', 'Conversation')} aria-live="polite" aria-relevant="additions text" aria-busy={busy}>
        <div className="nt-chat-row nt-chat-row-bot"><MascotHead size={38} /><div className="nt-chat-bubble"><p>{t('สวัสดี! วันนี้พักแถวไหนเอ่ย? บอกชื่อที่พักหรือจังหวัด แล้วเราช่วยหาที่เที่ยวกับคาเฟ่รอบ ๆ ให้ได้เลย', 'Hello! Where are you staying? Tell me your accommodation or province, and I’ll help you find nearby attractions and cafés.')}</p></div></div>
        {messages.map((message) => <div key={message.id} className={`nt-chat-row nt-chat-row-${message.role}`}>
          {message.role === 'bot' && <MascotHead size={38} />}
          <div className="nt-chat-bubble">
            {message.text && <p className="nt-chat-text">{message.text.split('\n').map((ln) => numberCitations(ln, message.sources)).join('\n')}</p>}
            {message.status === 'searching' && !message.text && <p className="nt-chat-waiting">{t('กำลังค้นสถานที่ให้…', 'Looking for places…')}</p>}
            {message.mode === 'llm' && <ResultCards result={message.places} t={t} lang={lang} />}
            {message.lodgings && <div className="nt-chat-lodgings">
              <h3>{t('เลือกที่พักของคุณ', 'Choose your accommodation')}</h3>
              {message.lodgings.validation?.ok === false && <p className="nt-chat-error" role="alert">{t('ผลค้นที่พักยังไม่ผ่านการตรวจสอบ จึงยังไม่แสดงรายการ', 'These accommodation results could not be verified, so they are hidden.')}</p>}
              {(message.lodgings.notices ?? []).map((notice, index) => <p key={index}>{noticeText(notice, lang)}</p>)}
              {message.lodgings.validation?.ok !== false && (message.lodgings.items ?? []).map((lodging) => <button key={lodging.id} type="button" onClick={() => chooseLodging(lodging)} disabled={busy || !Number.isFinite(lodging.lat) || !Number.isFinite(lodging.lon)}><strong>{lodging.name}</strong>{lodging.address && <small>{lodging.address}</small>}</button>)}
            </div>}
            <SourceCards sources={message.sources} t={t} />
            {message.status === 'stopped' && <p className="nt-chat-waiting">{t('หยุดรอคำตอบแล้ว ถามใหม่ได้เลย', 'Stopped waiting. Feel free to ask again.')}</p>}
            {message.error && <p className="nt-chat-error" role="alert">{message.error}</p>}
          </div>
        </div>)}
      </div>
      <div className="nt-chat-suggestions" aria-label={t('คำถามแนะนำ', 'Suggested questions')}>{suggestions.map(([thai, english]) => <button key={thai} type="button" disabled={busy} onClick={() => send(t(thai, english))}>{t(thai, english)} <span aria-hidden="true">↗</span></button>)}</div>
      <form className="nt-chat-composer" onSubmit={(event) => { event.preventDefault(); send(text); }}>
        <label className="nt-chat-input-label" htmlFor="chat-message">{t('ข้อความถึงน้องทริป', 'Message NongTrip')}{text.length >= 400 && <small className="nt-chat-count"> · {text.length}/500</small>}</label>
        <div><input ref={input} id="chat-message" value={text} onChange={(event) => setText(event.target.value)} maxLength={500} required placeholder={t('บอกชื่อที่พัก หรือพิมพ์คำถามได้เลย…', 'Your accommodation or question…')} autoComplete="off" />{busy && <button type="button" className="nt-chat-stop" onClick={stop}>{t('หยุด', 'Stop')}</button>}<button type="submit" disabled={busy || !text.trim()}>{busy ? t('กำลังตอบ…', 'Replying…') : t('ส่งข้อความ', 'Send')} <span aria-hidden="true">↑</span></button></div>
      </form>
    </div>
  </section>;
}
