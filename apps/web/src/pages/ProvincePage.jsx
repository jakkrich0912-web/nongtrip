import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import CatIcon from '../components/CatIcon.jsx';
import FavButton from '../components/FavButton.jsx';
import { provincePlaces } from '../lib/api.js';
import { subtypeLabel, iconGroup, placeName } from '../lib/data.js';
import { latestOnly } from '../lib/latest.js';
import { useLanguage } from '../lib/language.jsx';
import { useShareCompanionHint } from '../lib/companionContext.jsx';

const PAGE = 50;

// หน้าจังหวัด GET /api/provinces/{ชื่อ}/places (ข้อ 3.5)
// แสดงเฉพาะสถานที่ที่ตรวจที่มาแล้ว จังหวัดที่ยังไม่มีข้อมูลไม่ใช่ข้อผิดพลาด
// key ตามชื่อจังหวัด: เปลี่ยนจังหวัดแล้วเริ่มใหม่หมด ไม่มีหมวดหรือข้อความของจังหวัดเดิมค้าง
export default function ProvincePage() {
  const { name } = useParams();
  return <ProvinceBody key={name} name={name} />;
}

function ProvinceBody({ name }) {
  const { t, lang } = useLanguage();
  useShareCompanionHint({ province: name });
  const [category, setCategory] = useState('');
  const [state, setState] = useState({ status: 'loading', items: [] });
  const [note, setNote] = useState('');
  const seq = useRef(latestOnly()).current;
  useEffect(() => () => seq.cancel(), []); // eslint-disable-line react-hooks/exhaustive-deps

  const load = (offset = 0) => {
    // ทุกคำขอได้ token ใหม่ เปลี่ยนตัวกรองระหว่างโหลดเพิ่ม ผลเก่าจะถูกทิ้ง
    const token = seq.next();
    const stale = () => !seq.isCurrent(token);
    setState((s) => ({ ...s, status: offset ? 'more' : 'loading', ...(offset ? {} : { items: [] }) }));
    provincePlaces(name, { category: category || undefined, limit: PAGE, offset })
      .then((d) => {
        if (stale()) return;
        setState((s) => ({
          status: 'ok', ...d,
          // categories นับทั้งจังหวัด ไม่ขึ้นกับตัวกรอง เก็บของครั้งแรกไว้ทำปุ่ม
          allCategories: s.allCategories && category ? s.allCategories : d.categories,
          items: offset ? [...s.items, ...d.items] : d.items,
        }));
      })
      .catch((e) => {
        if (stale()) return;
        setState({ status: 'error', items: [], message: e.message, bad: e.status === 400 });
      });
  };
  useEffect(() => { load(0); }, [name, category]); // eslint-disable-line react-hooks/exhaustive-deps

  if (state.status === 'error') {
    return (
      <div className="page-pad empty">
        <Mascot size={110} mood="think" />
        <strong>{state.bad ? t('ไม่รู้จักจังหวัดนี้', 'We do not know this province') : t('เปิดหน้านี้ไม่ได้ตอนนี้', 'This page is unavailable right now')}</strong>
        <p>{state.message}</p>
        <Link className="btn small" to="/">{t('เลือกจังหวัดใหม่', 'Choose another province')}</Link>
      </div>
    );
  }

  const cats = Object.entries(state.allCategories ?? state.categories ?? {}).sort((a, b) => b[1] - a[1]);
  const searchLink = `/search?province=${encodeURIComponent(name)}`;

  return (
    <div className="prov-page page-pad">
      <nav className="crumbs" aria-label={t('ตำแหน่งหน้า', 'Breadcrumb')}>
        <Link to="/">{t('หน้าแรก', 'Home')}</Link>
        {state.region && <><span aria-hidden="true">›</span><span>{lang === 'en' ? `${state.region} region` : `ภาค${state.region}`}</span></>}
      </nav>
      <header className="prov-head">
        <div>
          <h1>{name}</h1>
          <p className="note">
            {state.status === 'loading' && !state.verified_count ? t('กำลังโหลด', 'Loading…') : t(`สถานที่ที่ตรวจที่มาแล้ว ${state.verified_count ?? 0} แห่ง`, `${state.verified_count ?? 0} places with verified sources`)}
          </p>
        </div>
        <Link className="btn" to={searchLink}>{t('ค้นรอบที่พักในจังหวัดนี้', 'Search around your stay here')}</Link>
      </header>

      {state.verified_count === 0 && state.status === 'ok' ? (
        <div className="empty">
          <Mascot size={110} mood="think" />
          <strong>{t('จังหวัดนี้ยังไม่มีสถานที่ที่ตรวจที่มาแล้ว', 'No verified places for this province yet')}</strong>
          <p>{t('ยังค้นที่เที่ยวรอบที่พักจากข้อมูล OpenStreetMap ได้ในหน้าค้นหา', 'You can still search around your stay with OpenStreetMap data on the search page.')}</p>
          <Link className="btn small" to={searchLink}>{t('ไปหน้าค้นหา', 'Go to search')}</Link>
        </div>
      ) : (
        <>
          {cats.length > 1 && (
            <div className="chips" role="group" aria-label={t('ประเภท', 'Type')}>
              <button className="chip" aria-pressed={!category} onClick={() => setCategory('')}>{t('ทั้งหมด', 'All')} {state.verified_count}</button>
              {cats.map(([c, n]) => (
                <button key={c} className="chip" aria-pressed={category === c} onClick={() => setCategory(c)}>
                  <CatIcon cat={iconGroup({ subtype: c })} size={14} /> {subtypeLabel(c, undefined, lang)} {n}
                </button>
              ))}
            </div>
          )}
          {note && <p className="notice" role="alert">{note}</p>}
          {state.status === 'loading' && <p className="note" role="status">{t('กำลังโหลด', 'Loading…')}</p>}
          <ul className="prov-grid-cards">
            {state.items.map((p) => {
              const g = iconGroup(p);
              return (
                <li key={p.id} className={`pcard c-${g}`}>
                  <Link to={`/places/${encodeURIComponent(p.id)}`} className="pcard-link">
                    <span className={`ico c-${g}`}><CatIcon cat={g} size={20} /></span>
                    <span className="pcard-body">
                      <strong>{placeName(p, lang)}</strong>
                      <small>{[subtypeLabel(p.subtype, p.kind, lang), p.area].filter(Boolean).join(' · ')}</small>
                      {p.description && <span className="pcard-desc">{p.description}</span>}
                    </span>
                  </Link>
                  <FavButton place={p} onError={setNote} />
                </li>
              );
            })}
          </ul>
          {state.has_more && (
            <div className="more">
              <button className="btn small" disabled={state.status === 'more'} onClick={() => load(state.items.length)}>
                {state.status === 'more' ? t('กำลังโหลด', 'Loading…') : t('โหลดเพิ่ม', 'Load more')}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
