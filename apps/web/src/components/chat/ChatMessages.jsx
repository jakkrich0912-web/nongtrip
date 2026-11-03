import MascotHead from '../MascotHead.jsx';
import SourceCards from './SourceCards.jsx';
import { noticeText } from '../../lib/notices.js';
import { numberCitations, safeUrl as safeSourceUrl } from '../../lib/chat.js';

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

// รายการข้อความทั้งหมด ใช้ทั้งหน้า /chat และหน้าต่างแชตของมาสคอต
export default function ChatMessages({ messages, busy, onChooseLodging, t, lang, headSize = 38 }) {
  return <div className="nt-chat-messages" role="log" aria-label={t('บทสนทนา', 'Conversation')} aria-live="polite" aria-relevant="additions text" aria-busy={busy}>
    <div className="nt-chat-row nt-chat-row-bot"><MascotHead size={headSize} /><div className="nt-chat-bubble"><p>{t('สวัสดี! วันนี้พักแถวไหนเอ่ย? บอกชื่อที่พักหรือจังหวัด แล้วเราช่วยหาที่เที่ยวกับคาเฟ่รอบ ๆ ให้ได้เลย', 'Hello! Where are you staying? Tell me your accommodation or province, and I’ll help you find nearby attractions and cafés.')}</p></div></div>
    {messages.map((message) => <div key={message.id} className={`nt-chat-row nt-chat-row-${message.role}`}>
      {message.role === 'bot' && <MascotHead size={headSize} />}
      <div className="nt-chat-bubble">
        {message.text && <p className="nt-chat-text">{message.text.split('\n').map((ln) => numberCitations(ln, message.sources)).join('\n')}</p>}
        {message.status === 'searching' && !message.text && <p className="nt-chat-waiting">{t('กำลังค้นสถานที่ให้…', 'Looking for places…')}</p>}
        {message.mode === 'llm' && <ResultCards result={message.places} t={t} lang={lang} />}
        {message.lodgings && <div className="nt-chat-lodgings">
          <h3>{t('เลือกที่พักของคุณ', 'Choose your accommodation')}</h3>
          {message.lodgings.validation?.ok === false && <p className="nt-chat-error" role="alert">{t('ผลค้นที่พักยังไม่ผ่านการตรวจสอบ จึงยังไม่แสดงรายการ', 'These accommodation results could not be verified, so they are hidden.')}</p>}
          {(message.lodgings.notices ?? []).map((notice, index) => <p key={index}>{noticeText(notice, lang)}</p>)}
          {message.lodgings.validation?.ok !== false && (message.lodgings.items ?? []).map((lodging) => <button key={lodging.id} type="button" onClick={() => onChooseLodging(lodging)} disabled={busy || !Number.isFinite(lodging.lat) || !Number.isFinite(lodging.lon)}><strong>{lodging.name}</strong>{lodging.address && <small>{lodging.address}</small>}</button>)}
        </div>}
        <SourceCards sources={message.sources} t={t} />
        {message.status === 'stopped' && <p className="nt-chat-waiting">{t('หยุดรอคำตอบแล้ว ถามใหม่ได้เลย', 'Stopped waiting. Feel free to ask again.')}</p>}
        {message.error && <p className="nt-chat-error" role="alert">{message.error}</p>}
      </div>
    </div>)}
  </div>;
}
