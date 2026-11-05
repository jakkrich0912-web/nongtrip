import { useState } from 'react';
import MascotHead from '../MascotHead.jsx';
import SourceCards from './SourceCards.jsx';
import { noticeText } from '../../lib/notices.js';
import { numberCitations, safeUrl as safeSourceUrl } from '../../lib/chat.js';
import { QUICK_PROVINCES } from '../../lib/useChatSession.js';
import { useTypewriter } from '../../lib/typewriter.js';
import { followUps } from '../../lib/followUps.js';

// คำตอบของน้องทริปพิมพ์ทีละตัว คำถามของผู้ใช้และคำตอบที่เสร็จก่อนเปิดหน้า (รวมจากประวัติ) แสดงทันที
function MessageText({ message }) {
  const full = message.text.split('\n').map((ln) => numberCitations(ln, message.sources)).join('\n');
  const [instant] = useState(() => message.role !== 'bot' || message.restored || message.status === 'done' || message.status === 'stopped');
  const [shown, typing] = useTypewriter(full, instant);
  return <p className={`nt-chat-text${typing ? ' is-typing' : ''}`}>{shown}</p>;
}

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

// แถบปุ่มใต้คำตอบ (หน้าแชตเต็มจอ): คัดลอก ถามใหม่ (เฉพาะคำตอบล่าสุด) และ 👍👎 (ล็อกอินแล้วและคำตอบถูกบันทึก)
function BotActions({ message, isLast, busy, session, t }) {
  const [copied, setCopied] = useState(false);
  if (!session || !message.text || !['done', 'stopped', 'error'].includes(message.status)) return null;
  const plain = message.text.split('\n').map((ln) => numberCitations(ln, message.sources)).join('\n').trim();
  const copy = async () => {
    try { await navigator.clipboard.writeText(plain); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* คัดลอกไม่ได้ (สิทธิ์เบราว์เซอร์) ไม่ต้องทำอะไร */ }
  };
  const rated = (v) => message.rating === v;
  return <div className="nt-chat-actions" role="group" aria-label={t('ตัวเลือกของคำตอบ', 'Answer options')}>
    <button type="button" onClick={copy} aria-label={t('คัดลอกคำตอบ', 'Copy answer')} title={t('คัดลอก', 'Copy')}>{copied ? '✓' : '⧉'}<span>{copied ? t('คัดลอกแล้ว', 'Copied') : t('คัดลอก', 'Copy')}</span></button>
    {isLast && <button type="button" onClick={session.regenerate} disabled={busy} aria-label={t('ถามใหม่อีกครั้ง', 'Regenerate')} title={t('ถามใหม่', 'Regenerate')}>↻<span>{t('ถามใหม่', 'Retry')}</span></button>}
    {session.canRate && message.serverId && <>
      <button type="button" aria-pressed={rated(1)} onClick={() => session.rate(message, 1)} aria-label={t('คำตอบนี้ดี', 'Good answer')} title={t('ดี', 'Good')}>👍</button>
      <button type="button" aria-pressed={rated(-1)} onClick={() => session.rate(message, -1)} aria-label={t('คำตอบนี้ไม่ดี', 'Bad answer')} title={t('ไม่ดี', 'Bad')}>👎</button>
    </>}
  </div>;
}

// แก้คำถามที่ส่งไปแล้ว: กล่องแก้แทนฟองข้อความ บันทึกแล้วถามใหม่ (คำตอบหลังจากนั้นหายไป)
function EditBox({ message, onCancel, onSave, t }) {
  const [draft, setDraft] = useState(message.text);
  const ok = draft.trim() && draft.trim().length <= 500;
  return <form className="nt-chat-edit" onSubmit={(e) => { e.preventDefault(); if (ok) onSave(draft.trim()); }}>
    <label className="ntg-sr" htmlFor={`edit-${message.id}`}>{t('แก้คำถาม', 'Edit question')}</label>
    <textarea id={`edit-${message.id}`} value={draft} maxLength={500} rows={2} autoFocus onChange={(e) => setDraft(e.target.value)}
      onKeyDown={(e) => { if (e.key === 'Escape') onCancel(); if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); if (ok) onSave(draft.trim()); } }} />
    <div><button type="button" onClick={onCancel}>{t('ยกเลิก', 'Cancel')}</button><button type="submit" disabled={!ok}>{t('ส่ง', 'Send')}</button></div>
  </form>;
}

// ปุ่มถามต่อใต้คำตอบล่าสุด กดแล้วถามต่อในแชตเดิมทันที
function FollowUps({ message, session, t }) {
  const list = followUps(message);
  if (!list.length) return null;
  return <div className="nt-chat-followups" role="group" aria-label={t('ถามต่อ', 'Follow-up questions')}>
    {list.map(([th, en]) => <button key={th} type="button" onClick={() => session.send(t(th, en))}>{t(th, en)}</button>)}
  </div>;
}

// รายการข้อความทั้งหมด ใช้ทั้งหน้า /chat และหน้าต่างแชตของมาสคอต
// ปุ่มตอบเมื่อน้องทริปถามว่าให้ค้นแถวไหน (done.ask = location): ใช้ตำแหน่งปัจจุบัน หรือเลือกจังหวัด
function AskLocation({ message, busy, session, t, lang }) {
  if (!session) return null;
  const { askHere, askInProvince, locating, locateError } = session;
  const q = message.question || '';
  return <div className="nt-chat-ask" role="group" aria-label={t('เลือกว่าจะค้นแถวไหน', 'Choose where to search')}>
    <button type="button" className="nt-chat-ask-here" disabled={busy || locating} onClick={() => askHere(q, t('ตำแหน่งปัจจุบัน', 'Current location'))}>
      <span aria-hidden="true">◎</span> {locating ? t('กำลังหาตำแหน่ง…', 'Finding you…') : t('ใช้ตำแหน่งปัจจุบันของฉัน', 'Use my current location')}
    </button>
    <div className="nt-chat-ask-provinces">{QUICK_PROVINCES.map(([th, en]) => <button key={th} type="button" disabled={busy} onClick={() => askInProvince(q, th, en)}>{lang === 'en' ? en : th}</button>)}</div>
    {locateError && <p className="nt-chat-ask-error" role="status">{locateError === 'unsupported' ? t('เบราว์เซอร์นี้หาตำแหน่งไม่ได้ ลองเลือกจังหวัดหรือพิมพ์ชื่อจังหวัดแทน', 'This browser cannot share your location. Choose or type a province instead.') : t('ใช้ตำแหน่งไม่ได้ (อาจยังไม่อนุญาต) ลองเลือกจังหวัดหรือพิมพ์ชื่อจังหวัดแทน', 'Could not get your location (permission may be off). Choose or type a province instead.')}</p>}
  </div>;
}

export default function ChatMessages({ messages, busy, onChooseLodging, t, lang, headSize = 38, session = null, greeting = true, actions = false }) {
  const lastId = messages[messages.length - 1]?.id;
  const lastBotId = [...messages].reverse().find((m) => m.role === 'bot')?.id;
  const [editing, setEditing] = useState(null);
  return <div className="nt-chat-messages" role="log" aria-label={t('บทสนทนา', 'Conversation')} aria-live="polite" aria-relevant="additions text" aria-busy={busy}>
    {greeting && <div className="nt-chat-row nt-chat-row-bot"><MascotHead size={headSize} /><div className="nt-chat-bubble"><p>{t('สวัสดี! วันนี้พักแถวไหนเอ่ย? บอกชื่อที่พักหรือจังหวัด แล้วเราช่วยหาที่เที่ยวกับคาเฟ่รอบ ๆ ให้ได้เลย', 'Hello! Where are you staying? Tell me your accommodation or province, and I’ll help you find nearby attractions and cafés.')}</p></div></div>}
    {messages.map((message) => (actions && message.role === 'user' && editing === message.id)
      ? <div key={message.id} className="nt-chat-row nt-chat-row-user"><EditBox message={message} t={t} onCancel={() => setEditing(null)} onSave={(v) => { setEditing(null); session.editAndResend(message, v); }} /></div>
      : <div key={message.id} className={`nt-chat-row nt-chat-row-${message.role}`}>
      {message.role === 'bot' && <MascotHead size={headSize} />}
      {actions && message.role === 'user' && !busy && <button type="button" className="nt-chat-edit-btn" onClick={() => setEditing(message.id)} aria-label={t('แก้คำถามนี้', 'Edit this question')} title={t('แก้คำถาม', 'Edit')}>✎</button>}
      <div className="nt-chat-bubble">
        {message.text && <MessageText message={message} />}
        {message.status === 'searching' && !message.text && <p className="nt-chat-waiting">{t('กำลังค้นสถานที่ให้…', 'Looking for places…')}</p>}
        {message.mode === 'llm' && <ResultCards result={message.places} t={t} lang={lang} />}
        {message.lodgings && <div className="nt-chat-lodgings">
          <h3>{t('เลือกที่พักของคุณ', 'Choose your accommodation')}</h3>
          {message.lodgings.validation?.ok === false && <p className="nt-chat-error" role="alert">{t('ผลค้นที่พักยังไม่ผ่านการตรวจสอบ จึงยังไม่แสดงรายการ', 'These accommodation results could not be verified, so they are hidden.')}</p>}
          {(message.lodgings.notices ?? []).map((notice, index) => <p key={index}>{noticeText(notice, lang)}</p>)}
          {message.lodgings.validation?.ok !== false && (message.lodgings.items ?? []).map((lodging) => <button key={lodging.id} type="button" onClick={() => onChooseLodging(lodging)} disabled={busy || !Number.isFinite(lodging.lat) || !Number.isFinite(lodging.lon)}><strong>{lodging.name}</strong>{lodging.address && <small>{lodging.address}</small>}</button>)}
        </div>}
        <SourceCards sources={message.sources} t={t} />
        {message.ask === 'location' && message.id === lastId && message.status === 'done' && <AskLocation message={message} busy={busy} session={session} t={t} lang={lang} />}
        {session && message.id === lastId && !busy && <FollowUps message={message} session={session} t={t} />}
        {message.status === 'stopped' && <p className="nt-chat-waiting">{t('หยุดรอคำตอบแล้ว ถามใหม่ได้เลย', 'Stopped waiting. Feel free to ask again.')}</p>}
        {message.error && <p className="nt-chat-error" role="alert">{message.error}</p>}
        {actions && message.role === 'bot' && <BotActions message={message} isLast={message.id === lastBotId} busy={busy} session={session} t={t} />}
      </div>
    </div>)}
  </div>;
}
