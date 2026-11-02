import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { MapContainer, TileLayer, Marker } from 'react-leaflet';
import L from 'leaflet';
import Mascot from '../components/Mascot.jsx';
import CatIcon from '../components/CatIcon.jsx';
import FavButton from '../components/FavButton.jsx';
import { placeById, placesNearby } from '../lib/api.js';
import { subtypeLabel, iconGroup } from '../lib/data.js';
import { mapsDirUrl } from '../lib/geo.js';

const pin = L.divIcon({
  className: '',
  html: '<span style="display:block;width:22px;height:22px;border-radius:50%;background:#B7472A;border:4px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,.35)"></span>',
  iconSize: [30, 30], iconAnchor: [15, 15],
});

const thaiDate = (iso) => {
  try { return new Date(`${iso}T00:00:00`).toLocaleDateString('th-TH', { day: 'numeric', month: 'long', year: 'numeric' }); }
  catch { return iso; }
};

// หน้ารายละเอียดสถานที่ GET /api/places/{id} (ข้อ 3.5)
// ฟิลด์ที่เป็น null ซ่อนทั้งส่วน ไม่เติมคำอธิบายเอง (CONTRACT ข้อ 1)
export default function PlaceDetail() {
  const { id } = useParams();
  const [state, setState] = useState({ status: 'loading' });
  const [near, setNear] = useState([]);
  const [note, setNote] = useState('');

  useEffect(() => {
    let alive = true;
    setState({ status: 'loading' }); setNear([]);
    placeById(id)
      .then((p) => {
        if (!alive) return;
        setState({ status: 'ok', place: p });
        // ที่เที่ยวใกล้เคียง (ไม่รวมตัวเอง) ถ้าค้นไม่ได้ก็ซ่อนส่วนนี้ไป
        placesNearby({ lat: p.lat, lon: p.lon, radius_km: 30, kinds: 'attraction', limit: 7 })
          .then((d) => alive && setNear(d.items.filter((x) => x.id !== p.id).slice(0, 6)))
          .catch(() => {});
      })
      .catch((e) => alive && setState({ status: 'error', message: e.message, notFound: e.status === 404 }));
    return () => { alive = false; };
  }, [id]);

  if (state.status === 'loading') return <p className="note page-pad" role="status">กำลังโหลด</p>;
  if (state.status === 'error') {
    return (
      <div className="page-pad empty">
        <Mascot size={110} mood="think" />
        <strong>{state.notFound ? 'ไม่พบสถานที่นี้' : 'เปิดหน้านี้ไม่ได้ตอนนี้'}</strong>
        <p>{state.message}</p>
        <Link className="btn small" to="/search">กลับไปค้นหา</Link>
      </div>
    );
  }

  const p = state.place;
  const g = iconGroup(p);
  const searchHere = `/search?lat=${p.lat}&lon=${p.lon}&name=${encodeURIComponent(p.name_th)}`;

  return (
    <article className="detail page-pad">
      <nav className="crumbs" aria-label="ตำแหน่งหน้า">
        <Link to="/">หน้าแรก</Link>
        {p.province && <><span aria-hidden="true">›</span><Link to={`/provinces/${encodeURIComponent(p.province)}`}>{p.province}</Link></>}
      </nav>

      <div className="detail-grid">
        <section className="detail-main">
          <header className="detail-head">
            <span className={`ico big c-${g}`}><CatIcon cat={g} size={26} /></span>
            <div>
              <h1>{p.name_th}</h1>
              {p.name_en && <p className="en">{p.name_en}</p>}
              <p className="meta">
                {subtypeLabel(p.subtype, p.kind)}
                {p.area && <> · {p.area}</>}
                {p.province && <> · {p.province}</>}
              </p>
            </div>
            <FavButton place={p} onError={setNote} className="big" />
          </header>
          {note && <p className="notice" role="alert">{note}</p>}

          <div className="detail-actions">
            <a className="btn" href={mapsDirUrl(p)} target="_blank" rel="noreferrer">นำทางด้วย Google Maps</a>
            {p.maps_url && <a className="btn ghost" href={p.maps_url} target="_blank" rel="noreferrer">ดูรีวิวที่ Google Maps</a>}
            <Link className="btn ghost" to={searchHere}>ดูที่เที่ยวรอบที่นี่</Link>
          </div>

          {p.description && (
            <section className="detail-block">
              <h2>เกี่ยวกับที่นี่</h2>
              <p>{p.description}</p>
            </section>
          )}

          {p.notes?.length > 0 && (
            <section className="detail-block">
              <h2>ควรรู้ก่อนไป</h2>
              <ul className="tips">{p.notes.map((n) => <li key={n}>{n}</li>)}</ul>
            </section>
          )}

          {(p.source_url || p.source_title) && (
            <section className="detail-block source">
              <h2>ที่มาของข้อมูล</h2>
              <p>
                ชื่อและพิกัดตรวจกับ{' '}
                {p.source_url
                  ? <a href={p.source_url} target="_blank" rel="noreferrer">{p.source_title ?? p.source_url}</a>
                  : p.source_title}
                {p.source_checked_on && <> เมื่อ {thaiDate(p.source_checked_on)}</>}
              </p>
              <p className="attr">ระบบไม่มีราคา ค่าเข้า หรือคะแนนรีวิว ดูรีวิวจริงได้ที่ Google Maps</p>
            </section>
          )}
        </section>

        <aside className="detail-side">
          <div className="detail-map">
            <MapContainer center={[p.lat, p.lon]} zoom={14} scrollWheelZoom={false} className="map">
              <TileLayer url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png" attribution="© OpenStreetMap contributors © CARTO" />
              <Marker position={[p.lat, p.lon]} icon={pin} />
            </MapContainer>
          </div>

          {near.length > 0 && (
            <section className="detail-block">
              <h2>ที่เที่ยวใกล้เคียง</h2>
              <ul className="near-list">
                {near.map((x) => {
                  const xg = iconGroup(x);
                  const inner = (
                    <>
                      <span className={`ico c-${xg}`}><CatIcon cat={xg} size={16} /></span>
                      <span className="nl-name">{x.name_th}<small>{subtypeLabel(x.subtype, x.kind)}</small></span>
                      <span className="nl-km">{x.distance_km} กม.<small>เส้นตรง</small></span>
                    </>
                  );
                  return (
                    <li key={x.id}>
                      {x.source === 'verified'
                        ? <Link to={`/places/${encodeURIComponent(x.id)}`}>{inner}</Link>
                        : <a href={x.maps_url ?? mapsDirUrl(x)} target="_blank" rel="noreferrer">{inner}</a>}
                    </li>
                  );
                })}
              </ul>
              {near.some((x) => x.source === 'osm') && <p className="attr">© OpenStreetMap contributors (ODbL)</p>}
            </section>
          )}
        </aside>
      </div>
    </article>
  );
}
