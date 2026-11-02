import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { PLACES, subtypeLabel, iconGroup } from '../lib/data.js';
import CatIcon from '../components/CatIcon.jsx';
import Mascot from '../components/Mascot.jsx';
import LodgingResults from '../components/LodgingResults.jsx';
import { lodgingsNear, placesNearby, ApiUnavailable } from '../lib/api.js';
import { placesAround, validateResults, mapsDirUrl, mapsSearchUrl, MAX_RADIUS_KM } from '../lib/geo.js';

const dot = (color, size) => L.divIcon({
  className: '',
  html: `<span style="display:block;width:${size}px;height:${size}px;border-radius:50%;background:${color};border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></span>`,
  iconSize: [size + 6, size + 6], iconAnchor: [(size + 6) / 2, (size + 6) / 2],
});
const homeIcon = dot('#F9A620', 18);
const placeIcon = dot('#B7472A', 12);
const activeIcon = dot('#4A7C59', 16);
const lodgeIcon = dot('#3D6A4B', 14);

function PinPicker({ onPick }) {
  useMapEvents({ click: (e) => onPick({ lat: e.latlng.lat, lon: e.latlng.lng }) });
  return null;
}
function FlyTo({ target }) {
  const map = useMap();
  useEffect(() => { if (target) map.flyTo([target.lat, target.lon], Math.max(map.getZoom(), 13), { duration: 0.6 }); }, [target, map]);
  return null;
}

export default function Search() {
  const [params] = useSearchParams();
  const province = params.get('province') ?? '';
  const inProv = PLACES.filter((p) => p.province === province);
  const center = inProv[0] ? [inProv[0].lat, inProv[0].lon] : [13.75, 100.5];

  const [origin, setOrigin] = useState(null);
  const [cat, setCat] = useState('');
  const [active, setActive] = useState(null);
  const [mode, setMode] = useState('booked'); // booked = มีที่พักแล้ว, browse = ยังไม่ได้จอง
  const [pin, setPin] = useState(null);
  const [lodging, setLodging] = useState({ status: 'idle' });
  // สถานที่รอบที่พักจาก GET /api/places/nearby ครั้งละ 100 แห่ง (เรียงใกล้ไปไกล)
  // ถ้าเปิด API ไม่ได้ ใช้สถานที่ที่ตรวจที่มาแล้วในเครื่องแทน และบอกผู้ใช้
  const [near, setNear] = useState({ status: 'idle', items: [] });
  const [kind, setKind] = useState('');
  const PAGE = 100;

  // กันผลเก่าทับผลใหม่: ทุกคำขอได้เลขลำดับ ผลที่กลับมาไม่ตรงเลขล่าสุดจะถูกทิ้ง
  // (ปักหมุดใหม่เร็วๆ หรือสลับประเภท แล้วคำตอบของหมุดเก่ามาช้ากว่า)
  const nearSeq = useRef(0);
  const lodgeSeq = useRef(0);
  const cancelPending = () => { nearSeq.current += 1; lodgeSeq.current += 1; };

  const loadNear = (o, k, offset = 0) => {
    const seq = offset ? nearSeq.current : ++nearSeq.current;
    const current = () => seq === nearSeq.current;
    setNear((n) => ({ ...n, status: offset ? 'more' : 'loading', ...(offset ? {} : { items: [] }) }));
    placesNearby({ lat: o.lat, lon: o.lon, kinds: k || undefined, limit: PAGE, offset })
      .then((d) => current() && setNear((n) => ({
        status: 'ok', source: 'api',
        items: offset ? [...n.items, ...d.items] : d.items,
        total: d.total, counts: d.counts, notices: d.notices ?? [], attribution: d.attribution,
        offset: d.offset + d.items.length,
      })))
      .catch((e) => {
        if (!current()) return;
        if (!(e instanceof ApiUnavailable)) { setNear({ status: 'error', items: [], message: e.message }); return; }
        const local = placesAround(o, PLACES, MAX_RADIUS_KM).filter((p) => !k || p.kind === k);
        setNear({
          status: 'ok', source: 'local', items: local, total: local.length, offset: local.length,
          counts: local.reduce((m, p) => ({ ...m, [p.kind]: (m[p.kind] ?? 0) + 1 }), {}),
          notices: ['ตอนนี้เชื่อมต่อระบบค้นไม่ได้ จึงแสดงเฉพาะสถานที่ที่ตรวจที่มาแล้วซึ่งมีจำนวนน้อย'],
        });
      });
  };
  useEffect(() => { if (origin) loadNear(origin, kind); }, [origin, kind]);

  const pick = (o) => {
    setActive(null);
    if (mode === 'booked') { setOrigin(o); return; }
    const seq = ++lodgeSeq.current;
    setPin(o); setOrigin(null); setLodging({ status: 'loading' });
    lodgingsNear(o)
      .then((data) => seq === lodgeSeq.current && setLodging({ status: 'ok', data }))
      .catch((e) => seq === lodgeSeq.current && setLodging({ status: 'error', message: e.message }));
  };
  const chooseLodging = (l) => { cancelPending(); setMode('booked'); setPin(null); setLodging({ status: 'idle' }); setOrigin({ lat: l.lat, lon: l.lon, name: l.name }); };
  const switchMode = (m) => { cancelPending(); setKind(''); setMode(m); setOrigin(null); setPin(null); setLodging({ status: 'idle' }); setActive(null); };

  const results = origin ? near.items : [];
  const check = validateResults(results);
  const mixOf = (list) => Object.entries(list.reduce((m, p) => ({ ...m, [iconGroup(p)]: (m[iconGroup(p)] ?? 0) + 1 }), {})).sort((x, y) => y[1] - x[1]);
  const provMix = mixOf(inProv);
  const KINDS = [['', 'ทั้งหมด'], ['attraction', 'ที่เที่ยว'], ['cafe', 'คาเฟ่']];
  const kindCount = (k) => (k ? near.counts?.[k] : Object.values(near.counts ?? {}).reduce((a, b) => a + b, 0));
  // แบ่งกลุ่มตามระยะ (ลำดับยังเรียงใกล้ไปไกลเหมือนเดิม)
  const groups = [[0, 5, 'ใน 5 กม.'], [5, 15, '5–15 กม.'], [15, 30.01, '15–30 กม.']]
    .map(([lo, hi, label]) => ({ label, items: results.filter((p) => p.distance_km >= lo && p.distance_km < hi) }))
    .filter((g) => g.items.length);

  return (
    <div className="search">
      <aside className="panel">
        <div className="panel-head">
          <div className="title-row">
            <h2>{province || 'รอบที่พัก'}</h2>
            {inProv.length > 0 && <span className="prov-n">{inProv.length} แห่งในจังหวัด</span>}
          </div>
          {inProv.length > 0 && (
            <div className="mix" aria-label="สัดส่วนประเภทในจังหวัด">
              {provMix.map(([c, n]) => (
                <span key={c} className={`seg c-${c}`} style={{ flexGrow: n }} title={`${n}`} />
              ))}
            </div>
          )}
          <div className="modes" role="tablist" aria-label="โหมดค้น">
            <button role="tab" aria-selected={mode === 'booked'} onClick={() => switchMode('booked')}>มีที่พักแล้ว</button>
            <button role="tab" aria-selected={mode === 'browse'} onClick={() => switchMode('browse')}>ยังไม่ได้จอง</button>
          </div>
          {mode === 'booked' && origin && (
            <div className="chips" role="group" aria-label="ประเภท">
              {KINDS.map(([k, label]) => (
                <button key={k} className="chip" aria-pressed={kind === k} onClick={() => setKind(k)}>
                  {k && <CatIcon cat={k === 'cafe' ? 'cafe' : 'temple'} size={14} />} {label}{near.counts && kind === '' ? ` ${kindCount(k) ?? 0}` : ''}
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="panel-body">
          {mode === 'browse' && <LodgingResults state={lodging} hasPin={!!pin} onChoose={chooseLodging} />}

          {mode === 'booked' && !origin && (
            <>
              <div className="hint-card">
                <Mascot size={58} mood="wave" className="hint-buddy" />
                <div>
                  <strong>แตะแผนที่ตรงที่พักของคุณ</strong>
                  <p>แล้วที่เที่ยวในรัศมี 30 กม. จะเรียงจากใกล้ไปไกลที่นี่</p>
                </div>
              </div>
              {province && inProv.length === 0 && <p className="notice">จังหวัดนี้ยังไม่มีสถานที่ที่ตรวจที่มาแล้วในระบบ</p>}
              {inProv.length > 0 && (
                <section className="spot">
                  <h3>ที่เที่ยวในจังหวัดนี้</h3>
                  <ul>
                    {inProv.slice(0, 6).map((p) => (
                      <li key={p.id}>
                        <button onClick={() => setActive(p)} aria-label={`ดู ${p.name_th} บนแผนที่`}>
                          <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={16} /></span>
                          <span>{p.name_th}<small>{subtypeLabel(p.subtype, p.kind)}</small></span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}

          {mode === 'booked' && origin && near.status === 'loading' && <p className="count" role="status">กำลังค้นที่เที่ยวรอบที่พัก</p>}
          {mode === 'booked' && origin && near.status === 'error' && (
            <div className="empty" role="status"><Mascot size={84} mood="think" /><strong>ค้นไม่ได้ตอนนี้</strong>{near.message}</div>
          )}
          {mode === 'booked' && origin && near.status !== 'loading' && near.status !== 'error' && !check.ok && <p className="err">ผลค้นไม่ผ่านการตรวจ จึงไม่แสดงผล ลองปักหมุดใหม่อีกครั้ง</p>}
          {mode === 'booked' && origin && (near.status === 'ok' || near.status === 'more') && check.ok && (
            <>
              {near.notices?.map((n) => <p key={n} className="notice">{n}</p>)}
              <p className="count">
                {origin.name ? <>รอบ <b>{origin.name}</b> · </> : null}
                <b>{near.total}</b> แห่งใน 30 กม. วัดเป็นระยะเส้นตรง
                {results.length < near.total ? ` (แสดง ${results.length} แห่งที่ใกล้สุด)` : ''}
              </p>
              {results.length === 0 && (
                <div className="empty"><Mascot size={84} mood="think" /><strong>ไม่พบสถานที่รอบจุดนี้</strong>ลองปักหมุดใกล้ตัวเมืองหรือเปลี่ยนประเภท</div>
              )}
              {groups.map((g) => (
                <section key={g.label} className="group">
                  <h4><span>{g.label}</span><small>{g.items.length} แห่ง</small></h4>
                  <ol className="track">
                    {g.items.map((p) => (
                      <li key={p.id} className={`c-${iconGroup(p)}`} data-active={active?.id === p.id} onClick={() => setActive(p)}>
                        <span className="km">{p.distance_km}<small>กม.<br />เส้นตรง</small></span>
                        <div className="place">
                          <h3>{p.name_th}</h3>
                          <div className="tags">
                            <span className="cat-tag"><CatIcon cat={iconGroup(p)} size={12} /> {subtypeLabel(p.subtype, p.kind)}</span>
                            {p.source === 'verified' && <span className="verified">ตรวจที่มาแล้ว</span>}
                          </div>
                          <div className="links">
                            <a className="go" href={p.directions_url ?? mapsDirUrl(p)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>นำทาง</a>
                            <a href={p.maps_url ?? mapsSearchUrl(p)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>ดูรีวิวที่ Google Maps</a>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                </section>
              ))}
              {results.length < near.total && (
                <div className="more">
                  <button className="btn small" disabled={near.status === 'more'} onClick={() => loadNear(origin, kind, near.offset)}>
                    {near.status === 'more' ? 'กำลังโหลด' : `โหลดเพิ่มอีก ${Math.min(PAGE, near.total - results.length)} แห่ง`}
                  </button>
                </div>
              )}
              {near.attribution && <p className="attr" style={{ padding: '0 20px 12px' }}>{near.attribution}</p>}
            </>
          )}
        </div>
      </aside>

      <div className="mapwrap">
      <div className="legend" aria-hidden="true">
        <span><i style={{ background: '#F9A620' }} />{mode === 'booked' ? 'ที่พักของคุณ' : 'ย่านที่เลือก'}</span>
        {mode === 'browse' && <span><i style={{ background: '#3D6A4B' }} />ที่พัก</span>}
        <span><i style={{ background: '#B7472A' }} />สถานที่</span>
        <span><i style={{ background: 'transparent', border: '2px dashed #4A7C59' }} />รัศมี {mode === 'booked' ? 30 : (lodging.data?.radius_km ?? 5)} กม.</span>
      </div>
      <MapContainer key={province} center={center} zoom={11} className="map">
        <TileLayer
          url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          attribution="© OpenStreetMap contributors © CARTO"
        />
        <PinPicker onPick={pick} />
        <FlyTo target={active} />
        {origin && (
          <>
            <Circle center={[origin.lat, origin.lon]} radius={30000} pathOptions={{ color: '#4A7C59', weight: 1.5, dashArray: '6 6', fillOpacity: 0.05 }} />
            <Marker position={[origin.lat, origin.lon]} icon={homeIcon}><Popup>ที่พักของคุณ</Popup></Marker>
          </>
        )}
        {pin && (
          <>
            <Circle center={[pin.lat, pin.lon]} radius={(lodging.data?.radius_km ?? 5) * 1000} pathOptions={{ color: '#3D6A4B', weight: 1.5, dashArray: '4 6', fillOpacity: 0.06 }} />
            <Marker position={[pin.lat, pin.lon]} icon={homeIcon}><Popup>ย่านที่เลือก</Popup></Marker>
          </>
        )}
        {lodging.status === 'ok' && lodging.data.items.map((l) => (
          <Marker key={l.id} position={[l.lat, l.lon]} icon={lodgeIcon} eventHandlers={{ click: () => chooseLodging(l) }}>
            <Popup>{l.name} · {l.distance_from_pin_km} กม.</Popup>
          </Marker>
        ))}
        {check.ok && results.map((p) => (
          <span key={p.id}>
            <Polyline positions={[[origin.lat, origin.lon], [p.lat, p.lon]]}
              pathOptions={{ color: active?.id === p.id ? '#4A7C59' : '#B7472A', weight: active?.id === p.id ? 2.5 : 1, opacity: 0.6, dashArray: '3 5' }} />
            <Marker position={[p.lat, p.lon]} icon={active?.id === p.id ? activeIcon : placeIcon}
              eventHandlers={{ click: () => setActive(p) }}>
              <Popup>{p.name_th} · {p.distance_km} กม.</Popup>
            </Marker>
          </span>
        ))}
      </MapContainer>
      </div>
    </div>
  );
}
