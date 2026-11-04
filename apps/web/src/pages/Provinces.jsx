import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import { provincesList } from '../lib/api.js';
import { PROVINCES, matchProvince, provinceLabel, regionLabel } from '../lib/provinces.js';
import { useLanguage } from '../lib/language.jsx';
import './info.css';

// กรองตามคำค้น ตัดภาคที่ไม่เหลือจังหวัดออก (ใช้ทั้งหน้าเว็บและเทสต์)
export function filterRegions(regions, query) {
  return (regions ?? [])
    .map((r) => ({ ...r, provinces: (r.provinces ?? []).filter((p) => matchProvince(p.name, query)) }))
    .filter((r) => r.provinces.length > 0);
}

// หน้ารวม 77 จังหวัด GET /api/provinces จัดตามภาค พร้อมจำนวนสถานที่ที่ตรวจแล้ว
// เรียก API ไม่ได้: ยังแสดงรายชื่อจังหวัดให้กดเข้าได้ แค่ไม่มีจำนวนและไม่แบ่งภาค
export default function Provinces() {
  const { t, lang } = useLanguage();
  const [state, setState] = useState({ status: 'loading', regions: [] });
  const [query, setQuery] = useState('');
  useEffect(() => {
    let live = true;
    provincesList()
      .then((d) => live && setState({ status: 'ok', regions: d.regions ?? [] }))
      .catch(() => live && setState({ status: 'offline', regions: [{ region: null, provinces: PROVINCES.map((name) => ({ name })) }] }));
    return () => { live = false; };
  }, []);

  const shown = useMemo(() => filterRegions(state.regions, query), [state.regions, query]);
  const total = shown.reduce((n, r) => n + r.provinces.length, 0);

  return (
    <div className="nti-page nt-container">
      <nav className="nti-crumbs" aria-label={t('ตำแหน่งหน้า', 'Breadcrumb')}>
        <Link to="/">{t('หน้าแรก', 'Home')}</Link><span aria-hidden="true">›</span><span>{t('ทุกจังหวัด', 'All provinces')}</span>
      </nav>
      <header className="nti-hero">
        <div>
          <span className="nt-eyebrow"><span />{t('77 จังหวัด', '77 PROVINCES')}</span>
          <h1>{t('เลือกจังหวัดที่จะไป', 'Pick a province')}</h1>
          <p>{t(
            'ทุกจังหวัดค้นรอบที่พักได้ด้วยข้อมูล OpenStreetMap จังหวัดที่มีตัวเลขสีเขียวมีสถานที่จากชุดข้อมูลที่ทีมตรวจที่มาแล้วด้วย กดเพื่อดูรายการทั้งจังหวัด',
            'Every province can be searched around a stay with OpenStreetMap data. A green count means the province also has places from the team’s verified dataset. Tap to see them all.',
          )}</p>
        </div>
        <Mascot size={130} mood="wave" interactive={false} />
      </header>

      <div className="nti-filter">
        <label>
          <span className="nt-sr-only">{t('ค้นหาจังหวัด', 'Find a province')}</span>
          <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
            placeholder={t('พิมพ์ชื่อจังหวัด ไทยหรืออังกฤษ', 'Type a province, Thai or English')} />
        </label>
        <p role="status">{state.status === 'loading' ? t('กำลังโหลด', 'Loading…') : t(`แสดง ${total} จังหวัด`, `Showing ${total} provinces`)}</p>
      </div>
      {state.status === 'offline' && <p className="notice">{t('ดึงจำนวนสถานที่ไม่ได้ตอนนี้ ยังกดเข้าแต่ละจังหวัดได้ตามปกติ', 'Counts are unavailable right now, but every province still opens.')}</p>}

      {state.status !== 'loading' && total === 0 && (
        <div className="nti-empty">
          <Mascot size={100} mood="think" interactive={false} />
          <strong>{t('ไม่พบจังหวัดนี้', 'No province matches')}</strong>
          <p>{t('ลองพิมพ์ชื่อสั้นลง เช่น "เชียง" หรือ "Chiang"', 'Try a shorter name, such as “Chiang”.')}</p>
        </div>
      )}

      {shown.map((r) => (
        <section key={r.region ?? 'all'} className="nti-region" aria-label={r.region ? regionLabel(r.region, lang) : t('ทุกจังหวัด', 'All provinces')}>
          {r.region && <h2>{regionLabel(r.region, lang)}<small>{t(`${r.provinces.length} จังหวัด`, `${r.provinces.length} provinces`)}</small></h2>}
          <ul className="nti-prov-grid">
            {r.provinces.map((p) => (
              <li key={p.name}>
                <Link className="nti-prov" to={`/provinces/${encodeURIComponent(p.name)}`}>
                  <strong>{provinceLabel(p.name, lang)}</strong>
                  <small>{lang === 'en' ? p.name : provinceLabel(p.name, 'en')}</small>
                  {p.verified_count > 0 && <span className="nti-badge">{t(`ตรวจแล้ว ${p.verified_count} แห่ง`, `${p.verified_count} verified`)}</span>}
                  {p.verified_count === 0 && <span className="nti-badge is-osm">{t('ข้อมูล OSM', 'OSM data')}</span>}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
