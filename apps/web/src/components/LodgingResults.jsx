import { categoryLabel } from '../lib/data.js';
import CatIcon from './CatIcon.jsx';
import Mascot from './Mascot.jsx';

// รายการที่พักรอบหมุด (โหมดยังไม่ได้จอง) ข้อมูลจาก GET /api/lodging/nearby
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
  const { items, meta } = state.data;
  return (
    <>
      {meta.notes?.map((n) => <p key={n} className="notice">{n}</p>)}
      {meta.osm_available === false && <p className="notice">ตอนนี้ดึงข้อมูลจาก OpenStreetMap ไม่ได้ แสดงเฉพาะข้อมูลที่ตรวจที่มาแล้ว</p>}
      <p className="count"><b>{items.length}</b> ที่พักในรัศมี {meta.radius_km} กม. วัดเป็นระยะเส้นตรง</p>
      {items.length === 0 && <div className="empty"><strong>ไม่พบที่พักรอบหมุดนี้</strong>ลองปักหมุดใกล้ตัวเมือง</div>}
      <ul className="lodges">
        {items.map((l) => (
          <li key={l.id} className="lodge">
            <div className="lodge-head">
              <h3>{l.name}</h3>
              <span className="lodge-km">{l.distance_km} กม.</span>
            </div>
            {l.source === 'osm' && <p className="attr">© OpenStreetMap contributors</p>}
            <ol className="mini">
              {(l.places_preview ?? []).map((p) => (
                <li key={p.id}>
                  <span className={`ico c-${p.category}`}><CatIcon cat={p.category} size={14} /></span>
                  <span>{p.name_th}<small>{categoryLabel(p.category)}</small></span>
                  <b>{p.distance_km} กม.</b>
                </li>
              ))}
            </ol>
            <button className="btn small" onClick={() => onChoose(l)}>
              เลือกที่พักนี้ · ดูทั้งหมด {l.places_total ?? 0} แห่ง
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
