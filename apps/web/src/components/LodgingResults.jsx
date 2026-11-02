import { subtypeLabel, iconGroup } from '../lib/data.js';
import CatIcon from './CatIcon.jsx';
import Mascot from './Mascot.jsx';

// รายการที่พักรอบหมุด (โหมดยังไม่ได้จอง) ข้อมูลจาก GET /api/lodgings/near
// รูปแบบคำตอบตาม docs/CONTRACT.md ข้อ 4 "คำตอบของ lodgings/near"
// ระบบไม่ตั้งที่พักให้จนกว่าผู้ใช้กดเลือกเอง (SPEC)
export default function LodgingResults({ state, hasPin, onChoose }) {
  if (!hasPin) {
    return (
      <div className="empty">
        <Mascot size={84} mood="wave" />
        <strong>ยังไม่ได้ปักหมุดย่าน</strong>
        แตะบนแผนที่ แล้วที่พักใน 5 กม. จะขึ้นที่นี่ พร้อมที่เที่ยวรอบแต่ละที่
      </div>
    );
  }
  if (state.status === 'loading') return <p className="count" role="status">กำลังค้นที่พักรอบหมุด</p>;
  if (state.status === 'error') {
    return (
      <div className="empty" role="status">
        <Mascot size={84} mood="think" />
        <strong>ค้นที่พักไม่ได้ตอนนี้</strong>
        {state.message} ระหว่างนี้ใช้โหมด "มีที่พักแล้ว" ปักหมุดตรงที่พักได้ก่อน
      </div>
    );
  }
  if (state.status !== 'ok') return null;
  const { items = [], radius_km: radius, notices = [], osm_available: osmAvailable, attribution } = state.data;
  return (
    <>
      {notices.map((n) => <p key={n} className="notice">{n}</p>)}
      {osmAvailable === false && <p className="notice">ตอนนี้ดึงข้อมูลจาก OpenStreetMap ไม่ได้ แสดงเฉพาะข้อมูลที่ตรวจที่มาแล้ว</p>}
      <p className="count"><b>{items.length}</b> ที่พักในรัศมี {radius} กม. วัดเป็นระยะเส้นตรง</p>
      {items.length === 0 && <div className="empty"><Mascot size={84} mood="think" /><strong>ไม่พบที่พักรอบหมุดนี้</strong>ลองปักหมุดใกล้ตัวเมือง</div>}
      <ul className="lodges">
        {items.map((l) => (
          <li key={l.id} className="lodge">
            <div className="lodge-head">
              <h3>{l.name}</h3>
              <span className="lodge-km">{l.distance_from_pin_km} กม. <small>(เส้นตรง)</small></span>
            </div>
            {l.subtype && <p className="attr">{subtypeLabel(l.subtype)}</p>}
            <ol className="mini">
              {(l.nearest ?? []).map((p) => (
                <li key={p.id}>
                  <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={14} /></span>
                  <span>{p.name_th}<small>{subtypeLabel(p.subtype, p.kind)}</small></span>
                  <b>{p.distance_km} กม.<small>เส้นตรง</small></b>
                </li>
              ))}
            </ol>
            <button className="btn small" onClick={() => onChoose(l)}>
              เลือกที่พักนี้ · ดูทั้งหมด {l.places_total ?? 0} แห่ง
            </button>
          </li>
        ))}
      </ul>
      {attribution && <p className="attr" style={{ padding: '0 22px 16px' }}>{attribution}</p>}
    </>
  );
}
