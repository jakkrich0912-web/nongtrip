import { subtypeLabel, iconGroup, placeName } from '../lib/data.js';
import { noticeText } from '../lib/notices.js';
import CatIcon from './CatIcon.jsx';
import Mascot from './Mascot.jsx';
import { useLanguage } from '../lib/language.jsx';

// รายการที่พักรอบหมุด (โหมดยังไม่ได้จอง) ข้อมูลจาก GET /api/lodgings/near
// รูปแบบคำตอบตาม docs/CONTRACT.md ข้อ 4 "คำตอบของ lodgings/near"
// ระบบไม่ตั้งที่พักให้จนกว่าผู้ใช้กดเลือกเอง (SPEC)
export default function LodgingResults({ state, hasPin, onChoose }) {
  const { t, lang } = useLanguage();
  if (!hasPin) {
    return (
      <div className="empty">
        <Mascot size={84} mood="wave" />
        <strong>{t('ยังไม่ได้ปักหมุดย่าน', 'No area pinned yet')}</strong>
        {t('แตะบนแผนที่ แล้วที่พักใน 5 กม. จะขึ้นที่นี่ พร้อมที่เที่ยวรอบแต่ละที่', 'Tap the map and stays within 5 km will appear here, with places around each one.')}
      </div>
    );
  }
  if (state.status === 'loading') return <p className="count" role="status">{t('กำลังค้นที่พักรอบหมุด', 'Looking for stays around the pin…')}</p>;
  if (state.status === 'error') {
    return (
      <div className="empty" role="status">
        <Mascot size={84} mood="think" />
        <strong>{t('ค้นที่พักไม่ได้ตอนนี้', 'Stay search is unavailable right now')}</strong>
        {state.message} {t('ระหว่างนี้ใช้โหมด "มีที่พักแล้ว" ปักหมุดตรงที่พักได้ก่อน', 'Meanwhile, use “I have a stay” and pin your stay directly.')}
      </div>
    );
  }
  if (state.status !== 'ok') return null;
  const { items = [], radius_km: radius, notices = [], osm_available: osmAvailable, attribution } = state.data;
  return (
    <>
      {notices.map((n) => <p key={n} className="notice">{noticeText(n, lang)}</p>)}
      {osmAvailable === false && <p className="notice">{t('ตอนนี้ดึงข้อมูลจาก OpenStreetMap ไม่ได้ แสดงเฉพาะข้อมูลที่ตรวจที่มาแล้ว', 'OpenStreetMap data is unavailable right now, so only verified data is shown.')}</p>}
      <p className="count"><b>{items.length}</b> {t('ที่พักในรัศมี', 'stays within')} {radius} {t('กม. วัดเป็นระยะเส้นตรง', 'km, straight-line distance')}</p>
      {items.length === 0 && <div className="empty"><Mascot size={84} mood="think" /><strong>{t('ไม่พบที่พักรอบหมุดนี้', 'No stays around this pin')}</strong>{t('ลองปักหมุดใกล้ตัวเมือง', 'Try a pin closer to town.')}</div>}
      <ul className="lodges">
        {items.map((l) => (
          <li key={l.id} className="lodge">
            <div className="lodge-head">
              <h3>{l.name}</h3>
              <span className="lodge-km">{l.distance_from_pin_km} {t('กม.', 'km')} <small>({t('เส้นตรง', 'straight-line')})</small></span>
            </div>
            {l.subtype && <p className="attr">{subtypeLabel(l.subtype, undefined, lang)}</p>}
            <ol className="mini">
              {(l.nearest ?? []).map((p) => (
                <li key={p.id}>
                  <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={14} /></span>
                  <span>{placeName(p, lang)}<small>{subtypeLabel(p.subtype, p.kind, lang)}</small></span>
                  <b>{p.distance_km} {t('กม.', 'km')}<small>{t('เส้นตรง', 'straight-line')}</small></b>
                </li>
              ))}
            </ol>
            <button className="btn small" onClick={() => onChoose(l)}>
              {t('เลือกที่พักนี้ · ดูทั้งหมด', 'Choose this stay · see all')} {l.places_total ?? 0} {t('แห่ง', 'places')}
            </button>
          </li>
        ))}
      </ul>
      {attribution && <p className="attr" style={{ padding: '0 22px 16px' }}>{attribution}</p>}
    </>
  );
}
