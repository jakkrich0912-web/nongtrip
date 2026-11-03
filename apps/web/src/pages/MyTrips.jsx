import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import CatIcon from '../components/CatIcon.jsx';
import { useAuth } from '../lib/auth.jsx';
import { subtypeLabel, iconGroup, placeName } from '../lib/data.js';
import { mapsDirUrl } from '../lib/geo.js';
import { useLanguage } from '../lib/language.jsx';
import {
  mySearches, deleteSearch, deleteAllSearches,
  myFavorites, removeFavorite, deleteAllFavorites,
  myChats, deleteChat, deleteAllChats, deleteAccount,
} from '../lib/api.js';

const fmt = (iso, lang = 'th') => {
  try { return new Date(iso).toLocaleDateString(lang === 'en' ? 'en-GB' : 'th-TH', { day: 'numeric', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
};

// ปุ่มลบสองจังหวะ: กดครั้งแรกถามยืนยัน กันลบพลาด
function ConfirmButton({ label, confirmLabel, onConfirm, className = 'linkbtn danger' }) {
  const { t } = useLanguage();
  const [ask, setAsk] = useState(false);
  if (!ask) return <button className={className} onClick={() => setAsk(true)}>{label}</button>;
  return (
    <span className="confirm">
      <button className="linkbtn danger strong" onClick={() => { setAsk(false); onConfirm(); }}>{confirmLabel}</button>
      <button className="linkbtn" onClick={() => setAsk(false)}>{t('ยกเลิก', 'Cancel')}</button>
    </span>
  );
}

// โหลดรายการจาก API พร้อมสถานะ ถ้าได้ 401 (session หมดอายุ) ส่งต่อให้ onExpired
function useList(loader, onExpired) {
  const [state, setState] = useState({ status: 'loading', items: [] });
  const load = () => loader()
    .then((d) => setState({ status: 'ok', items: d.items ?? [] }))
    .catch((e) => (e.status === 401 ? onExpired() : setState({ status: 'error', items: [], message: e.message })));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  return [state, setState, load];
}

function Section({ title, count, action, children }) {
  return (
    <section className="mt-card">
      <header>
        <h2>{title}{count != null && <small>{count}</small>}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}

function Status({ state, empty }) {
  const { t } = useLanguage();
  if (state.status === 'loading') return <p className="note" role="status">{t('กำลังโหลด', 'Loading…')}</p>;
  if (state.status === 'error') return <p className="auth-error" role="alert">{state.message}</p>;
  if (!state.items.length) return <p className="mt-empty">{empty}</p>;
  return null;
}

// หน้า "ทริปของฉัน": ที่พักที่เคยค้น สถานที่โปรด ประวัติแชต และจัดการบัญชี (ข้อ 3.3-3.4)
// รอรู้ก่อนว่าล็อกอินอยู่หรือไม่ ค่อยดึงรายการ (ไม่ยิงคำขอที่รู้อยู่แล้วว่าจะได้ 401)
export default function MyTrips() {
  const { user, ready } = useAuth();
  const { t } = useLanguage();
  if (!ready) return <p className="note" style={{ padding: 32 }} role="status">{t('กำลังโหลด', 'Loading…')}</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <MyTripsBody user={user} />;
}

function MyTripsBody({ user }) {
  const { t, lang } = useLanguage();
  const { logout, forget, setFavIds } = useAuth();
  const nav = useNavigate();
  // session หมดอายุระหว่างใช้งาน: ล้างสถานะผู้ใช้ แล้วพาไปหน้าเข้าสู่ระบบพร้อมบอกเหตุผล
  const expire = () => { forget(); nav('/login', { replace: true, state: { expired: true } }); };
  const [searches, setSearches] = useList(mySearches, expire);
  const [favs, setFavs] = useList(myFavorites, expire);
  const [chats, setChats] = useList(myChats, expire);
  const [error, setError] = useState('');
  const [delEmail, setDelEmail] = useState('');

  // ลบแล้วเอาออกจากหน้าจอทันที ถ้า API ไม่ยอมให้แสดงข้อความ
  const run = async (fn, after) => {
    setError('');
    try { await fn(); after(); } catch (e) { if (e.status === 401) expire(); else setError(e.message); }
  };
  const syncFavIds = (items) => setFavIds(new Set(items.map((i) => i.id)));

  return (
    <div className="mytrips">
      <div className="mt-hero">
        <Mascot size={92} mood="happy" />
        <div>
          <h1>{t('ทริปของฉัน', 'My trips')}</h1>
          <p className="note">{user.email}</p>
        </div>
        <button className="btn ghost" onClick={async () => { await logout(); nav('/'); }}>{t('ออกจากระบบ', 'Log out')}</button>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}

      <div className="mt-grid">
        <Section
          title={t('ที่พักที่เคยค้น', 'Stays you searched')} count={searches.items.length || null}
          action={searches.items.length > 0 && (
            <ConfirmButton label={t('ลบทั้งหมด', 'Delete all')} confirmLabel={t('ยืนยันลบทั้งหมด', 'Confirm delete all')}
              onConfirm={() => run(deleteAllSearches, () => setSearches({ status: 'ok', items: [] }))} />
          )}
        >
          <Status state={searches} empty={<>{t('ยังไม่มี ลองค้นที่พักใน', 'Nothing yet. Search for a stay on the ')}<Link to="/search">{t('หน้าค้นหา', 'search page')}</Link>{t(' ระบบจะจำไว้ให้', ' and we will remember it.')}</>} />
          <ul className="mt-list">
            {searches.items.map((s) => (
              <li key={s.id}>
                <Link className="mt-main" to={`/search?lat=${s.lat}&lon=${s.lon}&name=${encodeURIComponent(s.name)}`}>
                  <strong>{s.name}</strong>
                  <small>{t('ค้นเมื่อ', 'Searched')} {fmt(s.created_at, lang)}</small>
                </Link>
                <Link className="btn small" to={`/search?lat=${s.lat}&lon=${s.lon}&name=${encodeURIComponent(s.name)}`}>{t('ดูรอบที่พัก', 'View area')}</Link>
                <button className="icon-btn" aria-label={t(`ลบ ${s.name}`, `Delete ${s.name}`)}
                  onClick={() => run(() => deleteSearch(s.id), () => setSearches((st) => ({ ...st, items: st.items.filter((x) => x.id !== s.id) })))}>×</button>
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title={t('สถานที่โปรด', 'Favourite places')} count={favs.items.length || null}
          action={favs.items.length > 0 && (
            <ConfirmButton label={t('ลบทั้งหมด', 'Delete all')} confirmLabel={t('ยืนยันลบทั้งหมด', 'Confirm delete all')}
              onConfirm={() => run(deleteAllFavorites, () => { setFavs({ status: 'ok', items: [] }); syncFavIds([]); })} />
          )}
        >
          <Status state={favs} empty={t('ยังไม่มี กดรูปหัวใจบนการ์ดสถานที่ในหน้าค้นหาเพื่อเก็บไว้', 'Nothing yet. Tap the heart on a place card in search to save it.')} />
          <ul className="mt-list">
            {favs.items.map((p) => (
              <li key={p.id} className={`c-${iconGroup(p)}`}>
                <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={16} /></span>
                <div className="mt-main">
                  <strong>{p.source === 'verified' ? <Link to={`/places/${encodeURIComponent(p.id)}`}>{placeName(p, lang)}</Link> : placeName(p, lang)}</strong>
                  <small>{[subtypeLabel(p.subtype, p.kind, lang), p.province].filter(Boolean).join(' · ')}</small>
                  <span className="links">
                    <a className="go" href={mapsDirUrl(p)} target="_blank" rel="noreferrer">{t('นำทาง', 'Directions')}</a>
                    {p.maps_url && <a href={p.maps_url} target="_blank" rel="noreferrer">{t('ดูรีวิวที่ Google Maps', 'Reviews on Google Maps')}</a>}
                  </span>
                </div>
                <button className="icon-btn" aria-label={t(`เอา ${placeName(p, lang)} ออกจากสถานที่โปรด`, `Remove ${placeName(p, lang)} from favourites`)}
                  onClick={() => run(() => removeFavorite(p.id), () => setFavs((st) => {
                    const items = st.items.filter((x) => x.id !== p.id); syncFavIds(items); return { ...st, items };
                  }))}>×</button>
              </li>
            ))}
          </ul>
          {favs.items.some((p) => p.source === 'osm') && <p className="attr">© OpenStreetMap contributors (ODbL)</p>}
        </Section>

        <Section
          title={t('ประวัติแชต', 'Chat history')} count={chats.items.length || null}
          action={chats.items.length > 0 && (
            <ConfirmButton label={t('ลบทั้งหมด', 'Delete all')} confirmLabel={t('ยืนยันลบทั้งหมด', 'Confirm delete all')}
              onConfirm={() => run(deleteAllChats, () => setChats({ status: 'ok', items: [] }))} />
          )}
        >
          <Status state={chats} empty={<>{t('ยังไม่มี ลอง', 'Nothing yet. Try ')}<Link to="/chat">{t('ถามน้องทริป', 'asking NongTrip')}</Link>{t('ดูสิ', '.')}</>} />
          <ul className="mt-list">
            {chats.items.map((c) => (
              <li key={c.id}>
                <div className="mt-main">
                  <strong><Link to={`/chat?chat=${encodeURIComponent(c.id)}`}>{c.title}</Link></strong>
                  <small>{c.message_count} {t('ข้อความ', 'messages')} · {t('ล่าสุด', 'latest')} {fmt(c.updated_at, lang)}</small>
                </div>
                <button className="icon-btn" aria-label={t(`ลบแชต ${c.title}`, `Delete chat ${c.title}`)}
                  onClick={() => run(() => deleteChat(c.id), () => setChats((st) => ({ ...st, items: st.items.filter((x) => x.id !== c.id) })))}>×</button>
              </li>
            ))}
          </ul>
        </Section>

        <Section title={t('ลบบัญชี', 'Delete account')}>
          <p className="note">{t('ลบบัญชีและข้อมูลทั้งหมดถาวร ทั้งที่พักที่เคยค้น สถานที่โปรด และแชต กู้คืนไม่ได้ พิมพ์อีเมลของคุณเพื่อยืนยัน', 'This permanently deletes your account and all data: searched stays, favourites and chats. It cannot be undone. Type your email to confirm.')}</p>
          <form className="mt-delete" onSubmit={(e) => {
            e.preventDefault();
            run(() => deleteAccount(delEmail), () => { forget(); nav('/'); });
          }}>
            <input type="email" required placeholder={user.email} value={delEmail} onChange={(e) => setDelEmail(e.target.value)} aria-label={t('อีเมลยืนยันการลบบัญชี', 'Email to confirm account deletion')} />
            <button className="btn danger" disabled={delEmail.trim().toLowerCase() !== user.email.toLowerCase()}>{t('ลบบัญชีถาวร', 'Delete account permanently')}</button>
          </form>
        </Section>
      </div>
    </div>
  );
}
