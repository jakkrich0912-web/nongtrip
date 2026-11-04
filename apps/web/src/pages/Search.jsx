import { useEffect, useRef, useState } from 'react';
import { noticeText } from '../lib/notices.js';
import { Link, useSearchParams } from 'react-router-dom';
import { MapContainer, TileLayer, Marker, Popup, Polyline, Circle, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { PLACES, subtypeLabel, iconGroup, placeName } from '../lib/data.js';
import CatIcon from '../components/CatIcon.jsx';
import Mascot from '../components/Mascot.jsx';
import LodgingResults from '../components/LodgingResults.jsx';
import LodgingSearch from '../components/LodgingSearch.jsx';
import { lodgingsNear, placesNearby, ApiUnavailable, saveSearch } from '../lib/api.js';
import FavButton from '../components/FavButton.jsx';
import { useAuth } from '../lib/auth.jsx';
import { useShareCompanionHint } from '../lib/companionContext.jsx';
import { useLanguage } from '../lib/language.jsx';
import { provinceLabel } from '../lib/provinces.js';
import { placesAround, validateResults, mapsDirUrl, mapsSearchUrl, MAX_RADIUS_KM, RADIUS_OPTIONS, radiusComplete, withinRadius } from '../lib/geo.js';

const dot = (color, size) => L.divIcon({
  className: '',
  html: `<span style="display:block;width:${size}px;height:${size}px;border-radius:50%;background:${color};border:3px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.35)"></span>`,
  iconSize: [size + 6, size + 6], iconAnchor: [(size + 6) / 2, (size + 6) / 2],
});
const homeIcon = dot('#F9A620', 18);
const placeIcon = dot('#B7472A', 12);
const activeIcon = dot('#4A7C59', 16);
const lodgeIcon = dot('#3D6A4B', 14);
const candIcon = dot('#7B5A2E', 14);

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
  const { t, lang } = useLanguage();
  const [params] = useSearchParams();
  const province = params.get('province') ?? '';
  const inProv = PLACES.filter((p) => p.province === province);
  const center = inProv[0] ? [inProv[0].lat, inProv[0].lon] : [13.75, 100.5];

  // เปิดจาก "ทริปของฉัน" ได้ด้วย ?lat=&lon=&name= (ที่พักที่เคยค้น)
  const [origin, setOrigin] = useState(() => {
    const lat = parseFloat(params.get('lat')); const lon = parseFloat(params.get('lon'));
    return Number.isFinite(lat) && Number.isFinite(lon) ? { lat, lon, name: params.get('name') || undefined } : null;
  });
  useShareCompanionHint(origin);
  const { user } = useAuth();
  const [saveNote, setSaveNote] = useState('');
  const [cat, setCat] = useState('');
  const [active, setActive] = useState(null);
  const [mode, setMode] = useState('booked'); // booked = มีที่พักแล้ว, browse = ยังไม่ได้จอง
  const [pin, setPin] = useState(null);
  const [lodging, setLodging] = useState({ status: 'idle' });
  const [cands, setCands] = useState([]); // ที่พักที่ค้นเจอจากชื่อ รอผู้ใช้เลือก
  // สถานที่รอบที่พักจาก GET /api/places/nearby ครั้งละ 100 แห่ง (เรียงใกล้ไปไกล)
  // ถ้าเปิด API ไม่ได้ ใช้สถานที่ที่ตรวจที่มาแล้วในเครื่องแทน และบอกผู้ใช้
  const [near, setNear] = useState({ status: 'idle', items: [] });
  const [kind, setKind] = useState('');
  const [radius, setRadius] = useState(MAX_RADIUS_KM); // รัศมีที่เลือกกรอง (กม.) ไม่เกิน 30
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
          notices: [t('ตอนนี้เชื่อมต่อระบบค้นไม่ได้ จึงแสดงเฉพาะสถานที่ที่ตรวจที่มาแล้วซึ่งมีจำนวนน้อย', 'The search service is unavailable, so only a small set of verified places is shown.')],
        });
      });
  };
  useEffect(() => { if (origin) loadNear(origin, kind); }, [origin, kind]);

  const pick = (o) => {
    setActive(null);
    if (mode === 'booked') { setOrigin(o); setCands([]); return; }
    const seq = ++lodgeSeq.current;
    setPin(o); setOrigin(null); setLodging({ status: 'loading' });
    lodgingsNear(o)
      .then((data) => seq === lodgeSeq.current && setLodging({ status: 'ok', data }))
      .catch((e) => seq === lodgeSeq.current && setLodging({ status: 'error', message: e.message }));
  };
  const chooseLodging = (l) => {
    cancelPending(); setRadius(MAX_RADIUS_KM); setMode('booked'); setPin(null); setLodging({ status: 'idle' }); setCands([]);
    setActive({ lat: l.lat, lon: l.lon }); setOrigin({ lat: l.lat, lon: l.lon, name: l.name });
    // ล็อกอินอยู่: จำที่พักที่เลือกไว้ใน "ทริปของฉัน" (ไม่ล็อกอินไม่บันทึกอะไร)
    if (user && l.name) saveSearch({ name: l.name, lat: l.lat, lon: l.lon }).catch(() => {});
  };
  const switchMode = (m) => { cancelPending(); setKind(''); setRadius(MAX_RADIUS_KM); setCands([]); setMode(m); setOrigin(null); setPin(null); setLodging({ status: 'idle' }); setActive(null); };

  const results = origin ? near.items : [];
  const check = validateResults(results);
  // กรองรัศมีฝั่งหน้าเว็บจากผลที่ได้มาแล้ว (เรียงใกล้ไปไกลอยู่แล้ว) ไม่เปลี่ยนข้อมูลจาก API
  const shown = withinRadius(results, radius);
  const radiusDone = radiusComplete(results, near.total ?? results.length, radius);
  const mixOf = (list) => Object.entries(list.reduce((m, p) => ({ ...m, [iconGroup(p)]: (m[iconGroup(p)] ?? 0) + 1 }), {})).sort((x, y) => y[1] - x[1]);
  const provMix = mixOf(inProv);
  const KINDS = [['', t('ทั้งหมด', 'All')], ['attraction', t('ที่เที่ยว', 'Attractions')], ['cafe', t('คาเฟ่', 'Cafés')]];
  const kindCount = (k) => (k ? near.counts?.[k] : Object.values(near.counts ?? {}).reduce((a, b) => a + b, 0));
  // แบ่งกลุ่มตามระยะ (ลำดับยังเรียงใกล้ไปไกลเหมือนเดิม)
  const groups = [[0, 5, t('ใน 5 กม.', 'Within 5 km')], [5, 15, t('5–15 กม.', '5–15 km')], [15, 30.01, t('15–30 กม.', '15–30 km')]]
    .map(([lo, hi, label]) => ({ label, items: shown.filter((p) => p.distance_km >= lo && p.distance_km < hi) }))
    .filter((g) => g.items.length);

  return (
    <div className="search">
      <aside className="panel">
        <div className="panel-head">
          <div className="title-row">
            <h2>{province ? provinceLabel(province, lang) : t('รอบที่พัก', 'Around your stay')}</h2>
            {inProv.length > 0 && <Link className="prov-n" to={`/provinces/${encodeURIComponent(province)}`}>{t(`ดูทั้งจังหวัด ${inProv.length} แห่ง`, `See all ${inProv.length} in this province`)}</Link>}
          </div>
          {inProv.length > 0 && (
            <div className="mix" aria-label={t('สัดส่วนประเภทในจังหวัด', 'Place types in this province')}>
              {provMix.map(([c, n]) => (
                <span key={c} className={`seg c-${c}`} style={{ flexGrow: n }} title={`${n}`} />
              ))}
            </div>
          )}
          <div className="modes" role="tablist" aria-label={t('โหมดค้น', 'Search mode')}>
            <button role="tab" aria-selected={mode === 'booked'} onClick={() => switchMode('booked')}>{t('มีที่พักแล้ว', 'I have a stay')}</button>
            <button role="tab" aria-selected={mode === 'browse'} onClick={() => switchMode('browse')}>{t('ยังไม่ได้จอง', 'Not booked yet')}</button>
          </div>
          {mode === 'booked' && !origin && (
            <LodgingSearch key={province} province={province} onChoose={chooseLodging} onResults={setCands} />
          )}
          {mode === 'booked' && origin && (
            <button className="linkbtn change" onClick={() => { setOrigin(null); setActive(null); }}>{t('เปลี่ยนที่พัก', 'Change stay')}</button>
          )}
          {mode === 'booked' && origin && (
            <div className="chips" role="group" aria-label={t('ประเภท', 'Type')}>
              {KINDS.map(([k, label]) => (
                <button key={k} className="chip" aria-pressed={kind === k} onClick={() => setKind(k)}>
                  {k && <CatIcon cat={k === 'cafe' ? 'cafe' : 'temple'} size={14} />} {label}{near.counts && kind === '' && radius === MAX_RADIUS_KM ? ` ${kindCount(k) ?? 0}` : ''}
                </button>
              ))}
            </div>
          )}
          {mode === 'booked' && origin && (
            <div className="chips chips-wrap" role="group" aria-label={t('รัศมีจากที่พัก (ระยะเส้นตรง)', 'Radius from your stay (straight-line)')}>
              {RADIUS_OPTIONS.map((r) => (
                <button key={r} className="chip" aria-pressed={radius === r} onClick={() => setRadius(r)}>
                  {t(`ไม่เกิน ${r} กม.`, `Within ${r} km`)}
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
                  <strong>{t('พิมพ์ชื่อที่พัก หรือแตะแผนที่', 'Type your stay or tap the map')}</strong>
                  <p>{t('แล้วที่เที่ยวในรัศมี 30 กม. จะเรียงจากใกล้ไปไกลที่นี่', 'Places within 30 km will appear here, nearest first.')}</p>
                </div>
              </div>
              {province && inProv.length === 0 && <p className="notice">{t('จังหวัดนี้ยังไม่มีสถานที่ที่ตรวจที่มาแล้วในระบบ', 'No verified places for this province yet.')}</p>}
              {inProv.length > 0 && (
                <section className="spot">
                  <h3>{t('ที่เที่ยวในจังหวัดนี้', 'Things to do in this province')}</h3>
                  <ul>
                    {inProv.slice(0, 6).map((p) => (
                      <li key={p.id}>
                        <button onClick={() => setActive(p)} aria-label={t(`ดู ${placeName(p, lang)} บนแผนที่`, `Show ${placeName(p, lang)} on the map`)}>
                          <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={16} /></span>
                          <span>{placeName(p, lang)}<small>{subtypeLabel(p.subtype, p.kind, lang)}</small></span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}

          {mode === 'booked' && origin && near.status === 'loading' && <p className="count" role="status">{t('กำลังค้นที่เที่ยวรอบที่พัก', 'Looking for places around your stay…')}</p>}
          {mode === 'booked' && origin && near.status === 'error' && (
            <div className="empty" role="status"><Mascot size={84} mood="think" /><strong>{t('ค้นไม่ได้ตอนนี้', 'Search is unavailable right now')}</strong>{near.message}</div>
          )}
          {mode === 'booked' && origin && near.status !== 'loading' && near.status !== 'error' && !check.ok && <p className="err">{t('ผลค้นไม่ผ่านการตรวจ จึงไม่แสดงผล ลองปักหมุดใหม่อีกครั้ง', 'These results failed our check, so they are hidden. Please drop the pin again.')}</p>}
          {mode === 'booked' && origin && (near.status === 'ok' || near.status === 'more') && check.ok && (
            <>
              {near.notices?.map((n) => <p key={n} className="notice">{noticeText(n, lang)}</p>)}
              {saveNote && <p className="notice" role="alert">{saveNote}</p>}
              {!user && <p className="attr" style={{ padding: '8px 20px 0' }}><Link to="/login">{t('เข้าสู่ระบบ', 'Log in')}</Link> {t('เพื่อเก็บสถานที่โปรดและจำที่พักที่ค้นไว้', 'to save favourite places and remember your stays')}</p>}
              <p className="count">
                {origin.name ? <>{t('รอบ', 'Around')} <b>{origin.name}</b> · </> : null}
                {radius === MAX_RADIUS_KM ? (
                  <>
                    <b>{near.total}</b> {t('แห่งใน 30 กม. วัดเป็นระยะเส้นตรง', 'places within 30 km, straight-line distance')}
                    {results.length < near.total ? t(` (แสดง ${results.length} แห่งที่ใกล้สุด)`, ` (showing the nearest ${results.length})`) : ''}
                  </>
                ) : (
                  <>
                    <b>{shown.length}</b> {t(`แห่งไม่เกิน ${radius} กม. วัดเป็นระยะเส้นตรง`, `places within ${radius} km, straight-line distance`)}
                    {radiusDone ? '' : t(' (แสดงเท่าที่โหลดแล้ว)', ' (loaded so far)')}
                  </>
                )}
              </p>
              {shown.length === 0 && results.length > 0 && radiusDone && (
                <div className="empty"><Mascot size={84} mood="think" /><strong>{t(`ไม่มีสถานที่ไม่เกิน ${radius} กม.`, `No places within ${radius} km`)}</strong>{t('ลองเพิ่มรัศมี', 'Try a larger radius.')}</div>
              )}
              {results.length === 0 && (
                <div className="empty"><Mascot size={84} mood="think" /><strong>{t('ไม่พบสถานที่รอบจุดนี้', 'No places around this point')}</strong>{t('ลองปักหมุดใกล้ตัวเมืองหรือเปลี่ยนประเภท', 'Try a pin closer to town or another type.')}</div>
              )}
              {groups.map((g) => (
                <section key={g.label} className="group">
                  <h4><span>{g.label}</span><small>{g.items.length} {t('แห่ง', 'places')}</small></h4>
                  <ol className="track">
                    {g.items.map((p) => (
                      <li key={p.id} className={`c-${iconGroup(p)}`} data-active={active?.id === p.id} onClick={() => setActive(p)}>
                        <span className="km">{p.distance_km}<small>{t('กม.', 'km')}<br />{t('เส้นตรง', 'straight')}</small></span>
                        <div className="place">
                          <div className="place-head">
                            <h3>{p.source === 'verified'
                              ? <Link to={`/places/${encodeURIComponent(p.id)}`} onClick={(e) => e.stopPropagation()}>{placeName(p, lang)}</Link>
                              : placeName(p, lang)}</h3>
                            <FavButton place={p} onError={setSaveNote} />
                          </div>
                          <div className="tags">
                            <span className="cat-tag"><CatIcon cat={iconGroup(p)} size={12} /> {subtypeLabel(p.subtype, p.kind, lang)}</span>
                            {p.source === 'verified' && <span className="verified">{t('ตรวจที่มาแล้ว', 'Source verified')}</span>}
                          </div>
                          <div className="links">
                            <a className="go" href={p.directions_url ?? mapsDirUrl(p)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{t('นำทาง', 'Directions')}</a>
                            <a href={p.maps_url ?? mapsSearchUrl(p)} target="_blank" rel="noreferrer" onClick={(e) => e.stopPropagation()}>{t('ดูรีวิวที่ Google Maps', 'Reviews on Google Maps')}</a>
                          </div>
                        </div>
                      </li>
                    ))}
                  </ol>
                </section>
              ))}
              {results.length < near.total && !radiusDone && (
                <div className="more">
                  <button className="btn small" disabled={near.status === 'more'} onClick={() => loadNear(origin, kind, near.offset)}>
                    {near.status === 'more' ? t('กำลังโหลด', 'Loading…') : t(`โหลดเพิ่มอีก ${Math.min(PAGE, near.total - results.length)} แห่ง`, `Load ${Math.min(PAGE, near.total - results.length)} more`)}
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
        <span><i style={{ background: '#F9A620' }} />{mode === 'booked' ? t('ที่พักของคุณ', 'Your stay') : t('ย่านที่เลือก', 'Chosen area')}</span>
        {mode === 'browse' && <span><i style={{ background: '#3D6A4B' }} />{t('ที่พัก', 'Stays')}</span>}
        {cands.length > 0 && <span><i style={{ background: '#7B5A2E' }} />{t('ที่พักที่ค้นเจอ', 'Stays found')}</span>}
        <span><i style={{ background: '#B7472A' }} />{t('สถานที่', 'Places')}</span>
        <span><i style={{ background: 'transparent', border: '2px dashed #4A7C59' }} />{t('รัศมี', 'Radius')} {mode === 'booked' ? radius : (lodging.data?.radius_km ?? 5)} {t('กม.', 'km')}</span>
      </div>
      <MapContainer key={province} center={center} zoom={11} className="map">
        <TileLayer
          url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        />
        <PinPicker onPick={pick} />
        <FlyTo target={active} />
        {origin && (
          <>
            <Circle center={[origin.lat, origin.lon]} radius={radius * 1000} pathOptions={{ color: '#4A7C59', weight: 1.5, dashArray: '6 6', fillOpacity: 0.05 }} />
            <Marker position={[origin.lat, origin.lon]} icon={homeIcon} title={origin.name ?? t('ที่พักของคุณ', 'Your stay')}><Popup>{origin.name ?? t('ที่พักของคุณ', 'Your stay')}</Popup></Marker>
          </>
        )}
        {pin && (
          <>
            <Circle center={[pin.lat, pin.lon]} radius={(lodging.data?.radius_km ?? 5) * 1000} pathOptions={{ color: '#3D6A4B', weight: 1.5, dashArray: '4 6', fillOpacity: 0.06 }} />
            <Marker position={[pin.lat, pin.lon]} icon={homeIcon} title={t('ย่านที่เลือก', 'Chosen area')}><Popup>{t('ย่านที่เลือก', 'Chosen area')}</Popup></Marker>
          </>
        )}
        {cands.map((l) => (
          <Marker key={`c-${l.id}`} position={[l.lat, l.lon]} icon={candIcon} title={l.name} eventHandlers={{ click: () => chooseLodging(l) }}>
            <Popup>{l.name}</Popup>
          </Marker>
        ))}
        {lodging.status === 'ok' && lodging.data.items.map((l) => (
          <Marker key={l.id} position={[l.lat, l.lon]} icon={lodgeIcon} title={l.name} eventHandlers={{ click: () => chooseLodging(l) }}>
            <Popup>{l.name} · {l.distance_from_pin_km} {t('กม.', 'km')}</Popup>
          </Marker>
        ))}
        {check.ok && shown.map((p) => (
          <span key={p.id}>
            <Polyline positions={[[origin.lat, origin.lon], [p.lat, p.lon]]}
              pathOptions={{ color: active?.id === p.id ? '#4A7C59' : '#B7472A', weight: active?.id === p.id ? 2.5 : 1, opacity: 0.6, dashArray: '3 5' }} />
            <Marker position={[p.lat, p.lon]} icon={active?.id === p.id ? activeIcon : placeIcon} title={placeName(p, lang)}
              eventHandlers={{ click: () => setActive(p) }}>
              <Popup>{placeName(p, lang)} · {p.distance_km} {t('กม.', 'km')}</Popup>
            </Marker>
          </span>
        ))}
      </MapContainer>
      </div>
    </div>
  );
}
