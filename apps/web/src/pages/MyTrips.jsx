import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import CatIcon from '../components/CatIcon.jsx';
import { useAuth } from '../lib/auth.jsx';
import { subtypeLabel, iconGroup } from '../lib/data.js';
import { mapsDirUrl } from '../lib/geo.js';
import {
  mySearches, deleteSearch, deleteAllSearches,
  myFavorites, removeFavorite, deleteAllFavorites,
  myChats, deleteChat, deleteAllChats, deleteAccount,
} from '../lib/api.js';

const fmt = (iso) => {
  try { return new Date(iso).toLocaleDateString('th-TH', { day: 'numeric', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
};

// ปุ่มลบสองจังหวะ: กดครั้งแรกถามยืนยัน กันลบพลาด
function ConfirmButton({ label, confirmLabel, onConfirm, className = 'linkbtn danger' }) {
  const [ask, setAsk] = useState(false);
  if (!ask) return <button className={className} onClick={() => setAsk(true)}>{label}</button>;
  return (
    <span className="confirm">
      <button className="linkbtn danger strong" onClick={() => { setAsk(false); onConfirm(); }}>{confirmLabel}</button>
      <button className="linkbtn" onClick={() => setAsk(false)}>ยกเลิก</button>
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
  if (state.status === 'loading') return <p className="note" role="status">กำลังโหลด</p>;
  if (state.status === 'error') return <p className="auth-error" role="alert">{state.message}</p>;
  if (!state.items.length) return <p className="mt-empty">{empty}</p>;
  return null;
}

// หน้า "ทริปของฉัน": ที่พักที่เคยค้น สถานที่โปรด ประวัติแชต และจัดการบัญชี (ข้อ 3.3-3.4)
// รอรู้ก่อนว่าล็อกอินอยู่หรือไม่ ค่อยดึงรายการ (ไม่ยิงคำขอที่รู้อยู่แล้วว่าจะได้ 401)
export default function MyTrips() {
  const { user, ready } = useAuth();
  if (!ready) return <p className="note" style={{ padding: 32 }} role="status">กำลังโหลด</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <MyTripsBody user={user} />;
}

function MyTripsBody({ user }) {
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
          <h1>ทริปของฉัน</h1>
          <p className="note">{user.email}</p>
        </div>
        <button className="btn ghost" onClick={async () => { await logout(); nav('/'); }}>ออกจากระบบ</button>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}

      <div className="mt-grid">
        <Section
          title="ที่พักที่เคยค้น" count={searches.items.length || null}
          action={searches.items.length > 0 && (
            <ConfirmButton label="ลบทั้งหมด" confirmLabel="ยืนยันลบทั้งหมด"
              onConfirm={() => run(deleteAllSearches, () => setSearches({ status: 'ok', items: [] }))} />
          )}
        >
          <Status state={searches} empty={<>ยังไม่มี ลองค้นที่พักใน<Link to="/search">หน้าค้นหา</Link> ระบบจะจำไว้ให้</>} />
          <ul className="mt-list">
            {searches.items.map((s) => (
              <li key={s.id}>
                <Link className="mt-main" to={`/search?lat=${s.lat}&lon=${s.lon}&name=${encodeURIComponent(s.name)}`}>
                  <strong>{s.name}</strong>
                  <small>ค้นเมื่อ {fmt(s.created_at)}</small>
                </Link>
                <Link className="btn small" to={`/search?lat=${s.lat}&lon=${s.lon}&name=${encodeURIComponent(s.name)}`}>ดูรอบที่พัก</Link>
                <button className="icon-btn" aria-label={`ลบ ${s.name}`}
                  onClick={() => run(() => deleteSearch(s.id), () => setSearches((st) => ({ ...st, items: st.items.filter((x) => x.id !== s.id) })))}>×</button>
              </li>
            ))}
          </ul>
        </Section>

        <Section
          title="สถานที่โปรด" count={favs.items.length || null}
          action={favs.items.length > 0 && (
            <ConfirmButton label="ลบทั้งหมด" confirmLabel="ยืนยันลบทั้งหมด"
              onConfirm={() => run(deleteAllFavorites, () => { setFavs({ status: 'ok', items: [] }); syncFavIds([]); })} />
          )}
        >
          <Status state={favs} empty="ยังไม่มี กดรูปหัวใจบนการ์ดสถานที่ในหน้าค้นหาเพื่อเก็บไว้" />
          <ul className="mt-list">
            {favs.items.map((p) => (
              <li key={p.id} className={`c-${iconGroup(p)}`}>
                <span className={`ico c-${iconGroup(p)}`}><CatIcon cat={iconGroup(p)} size={16} /></span>
                <div className="mt-main">
                  <strong>{p.source === 'verified' ? <Link to={`/places/${encodeURIComponent(p.id)}`}>{p.name_th}</Link> : p.name_th}</strong>
                  <small>{[subtypeLabel(p.subtype, p.kind), p.province].filter(Boolean).join(' · ')}</small>
                  <span className="links">
                    <a className="go" href={mapsDirUrl(p)} target="_blank" rel="noreferrer">นำทาง</a>
                    {p.maps_url && <a href={p.maps_url} target="_blank" rel="noreferrer">ดูรีวิวที่ Google Maps</a>}
                  </span>
                </div>
                <button className="icon-btn" aria-label={`เอา ${p.name_th} ออกจากสถานที่โปรด`}
                  onClick={() => run(() => removeFavorite(p.id), () => setFavs((st) => {
                    const items = st.items.filter((x) => x.id !== p.id); syncFavIds(items); return { ...st, items };
                  }))}>×</button>
              </li>
            ))}
          </ul>
          {favs.items.some((p) => p.source === 'osm') && <p className="attr">© OpenStreetMap contributors (ODbL)</p>}
        </Section>

        <Section
          title="ประวัติแชต" count={chats.items.length || null}
          action={chats.items.length > 0 && (
            <ConfirmButton label="ลบทั้งหมด" confirmLabel="ยืนยันลบทั้งหมด"
              onConfirm={() => run(deleteAllChats, () => setChats({ status: 'ok', items: [] }))} />
          )}
        >
          <Status state={chats} empty={<>ยังไม่มี ลอง<Link to="/chat">ถามน้องทริป</Link>ดูสิ</>} />
          <ul className="mt-list">
            {chats.items.map((c) => (
              <li key={c.id}>
                <div className="mt-main">
                  <strong>{c.title}</strong>
                  <small>{c.message_count} ข้อความ · ล่าสุด {fmt(c.updated_at)}</small>
                </div>
                <button className="icon-btn" aria-label={`ลบแชต ${c.title}`}
                  onClick={() => run(() => deleteChat(c.id), () => setChats((st) => ({ ...st, items: st.items.filter((x) => x.id !== c.id) })))}>×</button>
              </li>
            ))}
          </ul>
        </Section>

        <Section title="ลบบัญชี">
          <p className="note">ลบบัญชีและข้อมูลทั้งหมดถาวร ทั้งที่พักที่เคยค้น สถานที่โปรด และแชต กู้คืนไม่ได้ พิมพ์อีเมลของคุณเพื่อยืนยัน</p>
          <form className="mt-delete" onSubmit={(e) => {
            e.preventDefault();
            run(() => deleteAccount(delEmail), () => { forget(); nav('/'); });
          }}>
            <input type="email" required placeholder={user.email} value={delEmail} onChange={(e) => setDelEmail(e.target.value)} aria-label="อีเมลยืนยันการลบบัญชี" />
            <button className="btn danger" disabled={delEmail.trim().toLowerCase() !== user.email.toLowerCase()}>ลบบัญชีถาวร</button>
          </form>
        </Section>
      </div>
    </div>
  );
}
