import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Circle, CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet';
import { useLanguage } from '../../lib/language.jsx';
import { PLACES, subtypeLabel } from '../../lib/data.js';
import { placesAround } from '../../lib/geo.js';
import Icon from './Icon.jsx';
import head from '../../assets/mascot/head.webp';

const PROVINCES = [...new Set(PLACES.map(p => p.province))].sort((a, b) => a.localeCompare(b, 'th'));
const INITIAL = { lat: 18.7965, lon: 98.9677 };
const safeUrl = value => /^https?:\/\//i.test(value ?? '') ? value : null;
function Recenter({ center, radius, selected }) {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
    const d = radius / 111;
    map.fitBounds([[center.lat - d, center.lon - d], [center.lat + d, center.lon + d]], { padding: [16,16], animate: false });
  }, [map, center, radius]);
  useEffect(() => { if (selected) map.panTo([selected.lat, selected.lon], { animate: false }); }, [map, selected]);
  return null;
}
export function PlaceSources({ place }) {
  const { t } = useLanguage();
  const sources = place.sources ?? [];
  return <div className="nt-place-sources">{sources.filter(s => safeUrl(s.url)).map((s,i) => <a href={s.url} key={i} target="_blank" rel="noreferrer">{t('แหล่งที่มา', 'Source')}: {s.title || t('เปิดข้อมูล', 'Open reference')}<Icon name="external" size={11} />{s.license && <span> · {s.license}</span>}</a>)}</div>;
}
function DemoMap({ center, radius, places, selected, onSelect }) {
  const { t, lang } = useLanguage();
  const [tileError, setTileError] = useState(false);
  return <div className="nt-demo-map"><MapContainer center={[center.lat, center.lon]} zoom={11} scrollWheelZoom={false} className="nt-leaflet" aria-label={t('แผนที่สถานที่จากหมุดสาธิต', 'Places around the demo pin')}>
    <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution='Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors (ODbL)</a>' eventHandlers={{ tileerror: () => setTileError(true), tileload: () => setTileError(false) }} />
    {[30,20,10].map(km => <Circle key={km} center={[center.lat, center.lon]} radius={km * 1000} pathOptions={{ color: km === radius ? '#3D6A4B' : '#71876c', weight: km === radius ? 2 : 1, dashArray: '5 6', fillOpacity: km === radius ? .07 : 0 }} />)}
    <CircleMarker center={[center.lat, center.lon]} radius={9} pathOptions={{ color: '#fff', weight: 3, fillColor: '#c16a08', fillOpacity: 1 }}><Popup>{t('หมุดสาธิต ไม่ใช่ที่พักที่คุณเลือก', 'Demo pin, not your selected accommodation')}</Popup></CircleMarker>
    {places.map(p => <CircleMarker key={p.id} center={[p.lat,p.lon]} radius={selected?.id === p.id ? 10 : 6} pathOptions={{ color: '#fff', weight: 2, fillColor: p.kind === 'cafe' ? '#a25334' : '#3D6A4B', fillOpacity: 1 }} eventHandlers={{ click: () => onSelect(p) }}><Popup><strong>{lang === 'en' ? p.name_en || p.name_th : p.name_th}</strong><br />{p.distance_km} {t('กม. · ระยะเส้นตรงจากหมุดสาธิต', 'km · straight-line from demo pin')}<PlaceSources place={p}/></Popup></CircleMarker>)}
    <Recenter center={center} radius={radius} selected={selected} />
  </MapContainer><div className="nt-map-legend"><span /><b>{t('หมุดสาธิต', 'Demo pin')}</b><small>{t('วงรัศมีเส้นตรง', 'Straight-line rings')}: 10 / 20 / 30 {t('กม.', 'km')}</small></div>{tileError && <p className="nt-tile-notice" role="status">{t('โหลดพื้นแผนที่ไม่ได้ หมุดและระยะยังแสดงได้', 'Map tiles unavailable; markers and distances still work.')}</p>}</div>;
}
function DemoChat({ places, radius }) {
  const { t, lang } = useLanguage();
  const [topic, setTopic] = useState('all');
  const shown = places.filter(p => topic !== 'cafe' || p.kind === 'cafe').slice(0, 2);
  return <div className="nt-demo-chat"><div className="nt-chat-example-label">{t('บทสนทนาตัวอย่าง · ใช้รายการสถานที่ด้านล่าง', 'Example conversation · based on the places below')}</div><div className="nt-chat-question">{topic === 'cafe' ? t('มีคาเฟ่รอบหมุดนี้ไหม?', 'Any cafés near this pin?') : t('แถวนี้มีที่ไหนน่าไปบ้าง?', 'What can I explore around here?')}</div><div className="nt-demo-reply"><img src={head} alt=""/><div><strong>{t('น้องทริป', 'NongTrip')}</strong><p>{shown.length ? t('ลองเริ่มจากสถานที่เหล่านี้ในข้อมูลที่ตรวจแล้วนะ', 'Here are some places from the verified dataset.') : t('ยังไม่พบสถานที่ประเภทนี้ในรัศมีที่เลือก ลองเปลี่ยนตัวกรองนะ', 'No places of this kind in the selected radius. Try a different filter.')}</p>{shown.map(p => <article className="nt-chat-source" key={p.id}><strong>{lang === 'en' ? p.name_en || p.name_th : p.name_th}</strong><small>{p.distance_km} {t('กม. · ระยะเส้นตรงจากหมุดสาธิต', 'km · straight-line from demo pin')}</small><PlaceSources place={p}/><small>{p.sources?.[0]?.license ?? t('แหล่งข้อมูลไม่ได้ระบุสัญญาอนุญาต', 'License not supplied by this source')}</small></article>)}</div></div><div className="nt-demo-prompts"><button type="button" aria-pressed={topic === 'all'} onClick={() => setTopic('all')}>{t('ดูที่เที่ยว', 'Explore places')}</button><button type="button" aria-pressed={topic === 'cafe'} onClick={() => setTopic('cafe')}>{t('หาคาเฟ่', 'Find cafés')}</button></div><p className="nt-demo-chat-note">{t('รัศมีตัวอย่าง', 'Demo radius')} {radius} {t('กม. · ระยะเส้นตรง ไม่ใช่ระยะขับรถ', 'km · straight-line, not driving distance')}</p><Link className="nt-text-link" to="/chat">{t('ถามคำถามของคุณในหน้าแชต', 'Ask your own question in chat')}<Icon size={16}/></Link></div>;
}
export default function ExploreDemo() {
  const { t, lang } = useLanguage();
  const [province,setProvince] = useState('เชียงใหม่');
  const [kind,setKind] = useState('all');
  const [radius,setRadius] = useState(10);
  const [tab,setTab] = useState('search');
  const [selected,setSelected] = useState(null);
  const center = useMemo(() => { const p = PLACES.find(p => p.province === province); return province === 'เชียงใหม่' ? INITIAL : {lat:p.lat,lon:p.lon}; }, [province]);
  const places = useMemo(() => placesAround(center, PLACES, radius).filter(p => kind === 'all' || p.kind === kind), [center,radius,kind]);
  const visible = places;
  const changeProvince = value => {setProvince(value);setSelected(null);};
  return <section className="nt-demo-section nt-container" id="try-it"><div className="nt-demo-heading"><div><span className="nt-eyebrow">A LITTLE PREVIEW OF YOUR NEXT TRIP</span><h2>{t('ลองเลือกจังหวัด เปิดมุมใหม่ของทริป', 'A new perspective on your next trip.')}</h2></div><span className="nt-demo-hint">{t('กดลองเล่นได้เลย', 'Go on, give it a try')}<span>↙</span></span></div>
    <div className="nt-browser"><div className="nt-browser-bar"><div className="nt-browser-dots"><i/><i/><i/></div><span className="nt-browser-address"><Icon name="shield" size={12}/>nongtrip / explore</span><span className="nt-preview-label">{t('ภาพตัวอย่าง', 'Interactive preview')}</span></div>
    <div className="nt-demo-toolbar"><div className="nt-demo-tabs" role="group" aria-label={t('รูปแบบตัวอย่าง', 'Demo view')}><button type="button" aria-pressed={tab === 'search'} onClick={() => setTab('search')}><Icon name="search" size={17}/>{t('ค้นหารอบที่พัก', 'Explore nearby')}</button><button type="button" aria-pressed={tab === 'chat'} onClick={() => setTab('chat')}><Icon name="chat" size={17}/>{t('คุยกับน้องทริป', 'Chat with NongTrip')}</button></div><span className="nt-verified"><Icon name="check" size={14}/>{t('ข้อมูลสถานที่จริง', 'Real place data')}</span></div>
    <div className="nt-demo-filters"><label><Icon name="pin" size={18}/><span className="nt-sr-only">{t('เลือกจังหวัดตัวอย่าง', 'Choose demo province')}</span><select value={province} onChange={e => changeProvince(e.target.value)}>{PROVINCES.map(p => <option key={p} value={p}>{p}</option>)}</select></label><div className="nt-kind-buttons" role="group" aria-label={t('ประเภทสถานที่', 'Place type')}>{[['all',t('ทั้งหมด','All')],['attraction',t('ที่เที่ยว','Attractions')],['cafe',t('คาเฟ่','Cafés')]].map(([value,label]) => <button type="button" key={value} aria-pressed={kind === value} onClick={() => {setKind(value);setSelected(null);}}>{label}</button>)}</div><label className="nt-radius-label">{t('รัศมีเส้นตรง', 'Straight-line radius')}<select value={radius} onChange={e => {setRadius(Number(e.target.value));setSelected(null);}}>{[10,20,30].map(k => <option value={k} key={k}>{k} {t('กม.', 'km')}</option>)}</select></label></div>
    <div className="nt-demo-body"><div className="nt-demo-results">{tab === 'search' ? <><div className="nt-results-heading"><h3>{t('แวะที่ไหนดีนะ', 'Where shall we go?')}</h3><p>{t('ใกล้หมุดสาธิต · เรียงจากใกล้ไปไกล', 'Near the demo pin · nearest first')}</p></div><div className="nt-results-list" aria-live="polite">{visible.length ? visible.map(p => <article className={`nt-place ${selected?.id === p.id ? 'is-selected' : ''}`} key={p.id}><button type="button" className="nt-place-select" aria-pressed={selected?.id === p.id} onClick={() => setSelected(p)}><span className={`nt-place-icon ${p.kind === 'cafe' ? 'is-cafe' : ''}`}><Icon name={p.kind === 'cafe' ? 'cafe' : 'pin'} size={22}/></span><span><strong>{lang === 'en' ? p.name_en || p.name_th : p.name_th}</strong><small>{lang === 'en' ? p.kind === 'cafe' ? 'Café' : 'Attraction' : subtypeLabel(p.subtype,p.kind)}</small></span><span className="nt-distance"><b>{p.distance_km}</b> {t('กม.', 'km')}<small>{t('เส้นตรง', 'straight-line')}</small></span></button><PlaceSources place={p}/></article>) : <div className="nt-demo-empty"><Icon name="compass" size={30}/><p>{t('ยังไม่พบข้อมูลในตัวกรองนี้ ลองเพิ่มรัศมีหรือเลือกประเภทอื่น', 'No places match. Try a larger radius or another type.')}</p></div>}</div><p className="nt-results-count">{t('แสดง', 'Showing')} {visible.length} {t('จาก', 'of')} {places.length} {t('แห่งในข้อมูลที่ตรวจแล้ว', 'places in the verified dataset')}</p></> : <DemoChat places={places} radius={radius}/>}</div><DemoMap center={center} radius={radius} places={places} selected={selected} onSelect={setSelected}/></div>
    <div className="nt-demo-bottom"><span><Icon name="compass" size={15}/>{t('ระยะเส้นตรงจากหมุดสาธิต ไม่ใช่ระยะขับรถ', 'Straight-line from the demo pin, not driving distance')}</span><Link to={`/search?province=${encodeURIComponent(province)}`}>{t('เลือกที่พักของคุณ', 'Choose your own stay')}<Icon size={16}/></Link></div></div>
    <p className="nt-demo-disclosure">{t('หมุดและบทสนทนาเป็นตัวอย่าง ไม่ใช่ที่พักที่คุณเลือก • ชื่อ พิกัด และแหล่งที่มาของสถานที่มาจากข้อมูลจริงในโครงการ', 'The pin and conversation are examples, not your selected stay. Place names, coordinates, and references come from the project dataset.')}</p>
  </section>;
}



