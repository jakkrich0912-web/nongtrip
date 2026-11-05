import { useEffect, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import Icon from '../components/landing/Icon.jsx';
import { adminOverview, adminReports, resolveReport } from '../lib/api.js';
import { REPORT_REASONS } from '../components/ReportPlace.jsx';
import { useAuth } from '../lib/auth.jsx';
import { useLanguage } from '../lib/language.jsx';
import { provinceLabel, regionLabel } from '../lib/provinces.js';
import './admin.css';

// ชื่อกฎของด่านตรวจ (มาจาก services/api/answer_guard.py) เป็นภาษาอังกฤษ
const GUARD_EN = { 'ชื่อสถานที่': 'Place names', 'ที่มา': 'Citations', 'ระยะ': 'Distances', 'พิกัด': 'Coordinates', 'คำต้องห้าม': 'Forbidden words', 'ความยาว': 'Length', 'ภาษา': 'Language', 'รูปแบบ': 'Format', 'ว่าง': 'Empty answer' };

export const pct = (part, whole) => (whole > 0 ? Math.round((part / whole) * 100) : 0);
export const shortDay = (iso, lang) => {
  try { return new Date(`${iso}T00:00:00Z`).toLocaleDateString(lang === 'en' ? 'en-GB' : 'th-TH', { day: 'numeric', month: 'short', timeZone: 'UTC' }); }
  catch { return iso; }
};
// สเกลแกนตั้ง: ค่าสูงสุดปัดขึ้นเป็นเลขคู่กลม ๆ (2, 4, 6, 8, 10 × 10^n) เส้นกลางจึงเป็นจำนวนเต็มเสมอ อย่างน้อย 4
export function niceMax(v) {
  const x = Math.max(4, v);
  const p = 10 ** Math.floor(Math.log10(x));
  return [2, 4, 6, 8, 10].map((m) => m * p).find((m) => m >= x);
}

// หน้าแดชบอร์ดผู้ดูแล GET /api/admin/overview (CONTRACT ข้อ 3.6) ยอดรวมทั้งหมด ไม่มีข้อมูลรายคน
export default function Admin() {
  const { user, ready } = useAuth();
  const { t } = useLanguage();
  if (!ready) return <p className="note" style={{ padding: 32 }} role="status">{t('กำลังโหลด', 'Loading…')}</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <AdminBody />;
}

function AdminBody() {
  const { t, lang } = useLanguage();
  const [state, setState] = useState({ status: 'loading' });
  const load = () => {
    setState((s) => ({ ...s, status: s.data ? 'refresh' : 'loading' }));
    adminOverview().then((data) => setState({ status: 'ok', data })).catch((e) => setState({ status: e.status === 403 ? 'forbidden' : 'error', message: e.message }));
  };
  useEffect(() => { load(); }, []);

  if (state.status === 'forbidden') {
    return (
      <div className="adm-denied nt-container">
        <Mascot size={130} mood="think" interactive={false} />
        <h1>{t('หน้านี้สำหรับผู้ดูแลระบบ', 'This page is for administrators')}</h1>
        <p>{t('บัญชีของคุณยังไม่ได้เป็นผู้ดูแล ถ้าคิดว่าควรเข้าได้ ให้ผู้ดูแลเพิ่มอีเมลของคุณใน ADMIN_EMAILS', 'Your account is not an administrator. If you should have access, ask an administrator to add your email to ADMIN_EMAILS.')}</p>
        <Link className="btn" to="/me">{t('กลับทริปของฉัน', 'Back to My trips')}</Link>
      </div>
    );
  }
  if (state.status === 'error') return <div className="adm nt-container"><p className="auth-error" role="alert">{state.message}</p><button className="btn small" onClick={load}>{t('ลองใหม่', 'Retry')}</button></div>;
  if (!state.data) return <p className="note" style={{ padding: 32 }} role="status">{t('กำลังโหลด', 'Loading…')}</p>;

  const d = state.data;
  const u = d.usage;
  const llm = u.chat_modes.llm ?? 0;
  const at = new Date(d.generated_at).toLocaleString(lang === 'en' ? 'en-GB' : 'th-TH', { dateStyle: 'medium', timeStyle: 'short' });

  return (
    <div className="adm nt-container">
      <header className="adm-head">
        <div>
          <span className="nt-eyebrow"><span />{t('ผู้ดูแลระบบ', 'ADMIN')}</span>
          <h1>{t('ภาพรวมของน้องทริป', 'NongTrip at a glance')}</h1>
          <p>{t(`ยอดรวมทั้งระบบ ย้อนหลัง ${d.window_days} วัน ไม่มีข้อมูลของใครเป็นรายคน · อัปเดต ${at}`, `System-wide totals for the last ${d.window_days} days, with no per-person data · updated ${at}`)}</p>
        </div>
        <button className="btn ghost small" onClick={load} disabled={state.status === 'refresh'}>
          {state.status === 'refresh' ? t('กำลังโหลด', 'Loading…') : t('รีเฟรช', 'Refresh')}
        </button>
      </header>

      <section className="adm-tiles" aria-label={t('ตัวเลขหลัก', 'Key numbers')}>
        <Tile label={t('บัญชีผู้ใช้', 'Accounts')} value={d.users.users} note={t(`ใหม่ 7 วัน ${d.users.users_new} · Google ${d.users.users_google}`, `${d.users.users_new} new in 7 days · ${d.users.users_google} Google`)} />
        <Tile label={t('เข้าสู่ระบบอยู่', 'Signed in now')} value={d.users.users_signed_in} note={t(`${d.users.active_sessions} เซสชันที่ยังไม่หมดอายุ`, `${d.users.active_sessions} live sessions`)} />
        <Tile label={t(`แชต ${d.window_days} วัน`, `Chats, ${d.window_days} days`)} value={u.chat_total} note={u.chat_total ? t(`ตอบด้วย LLM ${pct(llm, u.chat_total)}%`, `${pct(llm, u.chat_total)}% answered by the LLM`) : t('ยังไม่มีแชต', 'No chats yet')} />
        <Tile label={t(`การค้น ${d.window_days} วัน`, `Searches, ${d.window_days} days`)} value={u.search_total} note={t('รวมค้นรอบจุดและปักหมุดหาที่พัก', 'Area searches and pin searches')} />
      </section>

      <div className="adm-grid">
        <Card title={t('แชตรายวัน', 'Chats per day')} sub={t('14 วันล่าสุด แยกตามวิธีตอบ', 'Last 14 days, by how they were answered')} wide>
          <DailyBars days={u.daily} series={[
            { key: 'llm', label: t('LLM ผ่านด่านตรวจ', 'LLM, passed checks'), cls: 's1' },
            { key: 'rule', label: t('ตอบแบบกฎ', 'Rule-based'), cls: 's2' },
          ]} />
        </Card>

        <Card title={t('การค้นรายวัน', 'Searches per day')} sub={t('14 วันล่าสุด', 'Last 14 days')}>
          <DailyBars days={u.daily} series={[{ key: 'search', label: t('การค้น', 'Searches'), cls: 's1' }]} />
        </Card>

        <Card title={t('เหตุที่ด่านตรวจตีตกคำตอบ', 'Why the checker rejected answers')} sub={t(`${d.window_days} วัน ระบบถอยไปตอบแบบกฎทุกครั้ง`, `${d.window_days} days; each fell back to a rule-based reply`)}>
          <RankBars rows={u.guard.map((r) => ({ label: lang === 'en' ? (GUARD_EN[r.key] ?? r.key) : r.key, n: r.n }))} empty={t('ยังไม่มีคำตอบที่โดนตีตก', 'No rejected answers yet')} />
        </Card>

        <Card title={t('จังหวัดที่ค้นบ่อย', 'Most searched provinces')} sub={t('ประมาณจากสถานที่ที่ตรวจแล้วที่ใกล้จุดค้นที่สุด', 'Estimated from the nearest verified place')}>
          <RankBars rows={u.top_provinces.map((r) => ({ label: r.key === 'ไม่ทราบ' ? t('ไม่ทราบจังหวัด', 'Unknown') : provinceLabel(r.key, lang), n: r.n }))} empty={t('ยังไม่มีการค้น', 'No searches yet')} />
        </Card>

        <Card title={t('คะแนนคำตอบ', 'Answer ratings')} sub={t('จากปุ่ม 👍👎 ใต้คำตอบ', 'From the 👍👎 buttons under answers')}>
          <Ratings r={d.ratings} />
        </Card>

        <Card title={t('สถานะระบบ', 'System status')} sub={t('ค่าตอนเปิดหน้านี้', 'As of loading this page')}>
          <ul className="adm-status">
            <Status ok={d.system.llm} label={t('แชตใช้ LLM', 'Chat uses the LLM')} on={t('เปิดอยู่', 'On')} off={t('ปิด ตอบแบบกฎ', 'Off, rule-based')} />
            <Status ok={d.system.osm_live} label={t('ค้น OpenStreetMap สด', 'Live OpenStreetMap')} on={t('เปิดอยู่', 'On')} off={t('ใช้ข้อมูลที่เก็บไว้', 'Using saved data')} neutral />
            <li><span className="adm-dot is-info" aria-hidden="true" /><span>{t('ก้อนความรู้ของแชต', 'Chat knowledge passages')}</span><b>{d.system.rag_docs.toLocaleString()}</b></li>
            <li><span className="adm-dot is-info" aria-hidden="true" /><span>{t('สถานที่ที่ตรวจที่มาแล้ว', 'Verified places')}</span><b>{d.system.verified_places.toLocaleString()}</b></li>
            {d.system.snapshot_built_on && <li><span className="adm-dot is-info" aria-hidden="true" /><span>{t('ข้อมูล OSM ที่เก็บไว้ ดึงเมื่อ', 'Saved OSM data fetched')}</span><b>{d.system.snapshot_built_on}</b></li>}
          </ul>
        </Card>

        <Card title={t('ข้อมูลที่ผู้ใช้เก็บไว้', 'What users keep')} sub={t('ทั้งระบบ', 'Whole system')}>
          <dl className="adm-kv">
            <div><dt>{t('ที่พักที่บันทึก', 'Saved stays')}</dt><dd>{d.content.saved_searches.toLocaleString()}</dd></div>
            <div><dt>{t('สถานที่โปรด', 'Favourites')}</dt><dd>{d.content.favorites.toLocaleString()}</dd></div>
            <div><dt>{t('แชต', 'Chats')}</dt><dd>{d.content.chats.toLocaleString()}</dd></div>
            <div><dt>{t('ข้อความ', 'Messages')}</dt><dd>{d.content.messages.toLocaleString()}</dd></div>
          </dl>
          <h3 className="adm-h3">{t('สถานที่ที่คนบันทึกเป็นโปรดมากสุด', 'Most saved places')}</h3>
          {d.top_favorites.length
            ? <ol className="adm-list">{d.top_favorites.map((f) => <li key={f.name_th}><span>{f.name_th}{f.province && <small> · {provinceLabel(f.province, lang)}</small>}</span><b>{f.n}</b></li>)}</ol>
            : <p className="adm-empty">{t('แสดงเมื่อมีสถานที่ที่บันทึกตั้งแต่ 2 บัญชีขึ้นไป', 'Shown once a place is saved by 2 or more accounts')}</p>}
        </Card>

        <Reports />

        <Card title={t('ความครอบคลุมข้อมูล', 'Data coverage')} sub={t(`${d.coverage.provinces} จังหวัด`, `${d.coverage.provinces} provinces`)} wide>
          <div className="adm-cover">
            <Meter label={t('มีข้อมูล OSM เก็บไว้ (ค้นได้แม้เน็ตช้า)', 'Saved OSM data (works on slow networks)')} n={d.coverage.with_snapshot} of={d.coverage.provinces} />
            <Meter label={t('มีสถานที่ที่ตรวจที่มาแล้ว', 'Has verified places')} n={d.coverage.with_verified} of={d.coverage.provinces} />
          </div>
          {d.coverage.missing_snapshot.length > 0 && <>
            <h3 className="adm-h3">{t(`ยังไม่มีข้อมูล OSM เก็บไว้ ${d.coverage.missing_snapshot.length} จังหวัด`, `${d.coverage.missing_snapshot.length} provinces without saved OSM data`)}</h3>
            <ul className="adm-chips">{d.coverage.missing_snapshot.map((p) => <li key={p}><Link to={`/provinces/${encodeURIComponent(p)}`}>{provinceLabel(p, lang)}</Link></li>)}</ul>
          </>}
          <details className="adm-table">
            <summary>{t('ดูรายจังหวัดเป็นตาราง', 'Show every province as a table')}</summary>
            <table>
              <thead><tr><th>{t('ภาค', 'Region')}</th><th>{t('จังหวัด', 'Province')}</th><th>{t('ตรวจแล้ว (แห่ง)', 'Verified places')}</th><th>{t('ข้อมูล OSM เก็บไว้', 'Saved OSM data')}</th></tr></thead>
              <tbody>{d.coverage.regions.flatMap((r) => r.provinces.map((p) => (
                <tr key={p.name}><td>{regionLabel(r.region, lang)}</td><td>{provinceLabel(p.name, lang)}</td><td>{p.verified}</td><td>{p.snapshot ? t('มี', 'Yes') : t('ไม่มี', 'No')}</td></tr>
              )))}</tbody>
            </table>
          </details>
        </Card>
      </div>
    </div>
  );
}

// รายการแจ้งข้อมูลผิด (v0.26) กดตรวจแล้วเพื่อลบออก ไม่มีข้อมูลว่าใครแจ้ง
function Reports() {
  const { t, lang } = useLanguage();
  const [state, setState] = useState({ status: 'loading', items: [], total: 0 });
  const [error, setError] = useState('');
  useEffect(() => {
    adminReports().then((d) => setState({ status: 'ok', items: d.items, total: d.total })).catch((e) => setState({ status: 'error', items: [], total: 0, message: e.message }));
  }, []);
  const reason = (id) => { const r = REPORT_REASONS.find((x) => x[0] === id); return r ? t(r[1], r[2]) : id; };
  const done = async (id) => {
    setError('');
    try { await resolveReport(id); setState((s) => ({ ...s, items: s.items.filter((x) => x.id !== id), total: s.total - 1 })); }
    catch (e) { setError(e.message); }
  };
  return (
    <Card title={t('แจ้งข้อมูลผิด', 'Problem reports')} sub={t(`รอตรวจ ${state.total} รายการ ตรวจแล้วกดลบ`, `${state.total} waiting; delete once checked`)} wide>
      {state.status === 'error' && <p className="auth-error" role="alert">{state.message}</p>}
      {error && <p className="auth-error" role="alert">{error}</p>}
      {state.status === 'ok' && !state.items.length && <p className="adm-empty">{t('ยังไม่มีรายการแจ้ง', 'No reports yet')}</p>}
      {state.items.length > 0 && (
        <ul className="adm-reports">
          {state.items.map((r) => (
            <li key={r.id}>
              <div>
                <strong>{r.place_id.startsWith('v:') ? <Link to={`/places/${encodeURIComponent(r.place_id)}`}>{r.place_name}</Link> : r.place_name}</strong>
                <small>{reason(r.reason)} · {r.place_id} · {shortDay(r.created_at.slice(0, 10), lang)}</small>
                {r.note && <p>{r.note}</p>}
              </div>
              <button type="button" className="btn small ghost" onClick={() => done(r.id)}>{t('ตรวจแล้ว ลบ', 'Checked, delete')}</button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function Tile({ label, value, note }) {
  return <div className="adm-tile"><span>{label}</span><b>{Number(value ?? 0).toLocaleString()}</b><small>{note}</small></div>;
}

function Card({ title, sub, wide, children }) {
  return <section className={`adm-card${wide ? ' is-wide' : ''}`}><header><h2>{title}</h2>{sub && <p>{sub}</p>}</header>{children}</section>;
}

// กราฟแท่งรายวัน (ซ้อนกันได้หลายชุด) วางเมาส์หรือโฟกัสแท่งแล้วเห็นตัวเลข มีตารางให้ดูแทนกราฟ
function DailyBars({ days, series }) {
  const { t, lang } = useLanguage();
  const [hover, setHover] = useState(null);
  const total = (d) => series.reduce((n, s) => n + (d[s.key] ?? 0), 0);
  const max = niceMax(Math.max(0, ...days.map(total)));
  const ticks = [max, max / 2, 0];
  return (
    <div className="adm-chart">
      {series.length > 1 && <ul className="adm-legend">{series.map((s) => <li key={s.key}><i className={s.cls} aria-hidden="true" />{s.label}</li>)}</ul>}
      <div className="adm-plot">
        <div className="adm-axis" aria-hidden="true">{ticks.map((v) => <span key={v}>{v}</span>)}</div>
        <div className="adm-bars" onMouseLeave={() => setHover(null)}>
          {days.map((d, i) => {
            const sum = total(d);
            return (
              <div key={d.day} className="adm-col" tabIndex={0} onMouseEnter={() => setHover(i)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
                aria-label={`${shortDay(d.day, lang)}: ${series.map((s) => `${s.label} ${d[s.key] ?? 0}`).join(', ')}`}>
                <div className="adm-stack" style={{ height: `${(sum / max) * 100}%` }}>
                  {series.map((s) => (d[s.key] ? <span key={s.key} className={s.cls} style={{ flexGrow: d[s.key] }} /> : null))}
                </div>
                {hover === i && (
                  <div className="adm-tip" role="presentation">
                    <strong>{shortDay(d.day, lang)}</strong>
                    {series.map((s) => <span key={s.key}><i className={s.cls} />{s.label}<b>{d[s.key] ?? 0}</b></span>)}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      <div className="adm-xlabels" aria-hidden="true">
        {days.map((d, i) => <span key={d.day}>{i % 2 === days.length % 2 ? shortDay(d.day, lang) : ''}</span>)}
      </div>
      <details className="adm-table">
        <summary>{t('ดูเป็นตาราง', 'Show as a table')}</summary>
        <table>
          <thead><tr><th>{t('วัน', 'Day')}</th>{series.map((s) => <th key={s.key}>{s.label}</th>)}</tr></thead>
          <tbody>{days.map((d) => <tr key={d.day}><td>{shortDay(d.day, lang)}</td>{series.map((s) => <td key={s.key}>{d[s.key] ?? 0}</td>)}</tr>)}</tbody>
        </table>
      </details>
    </div>
  );
}

// แท่งแนวนอนเรียงมากไปน้อย ชื่อและตัวเลขเป็นตัวหนังสือ ไม่ใช้สีบอกความหมาย
function RankBars({ rows, empty }) {
  if (!rows.length) return <p className="adm-empty">{empty}</p>;
  const max = Math.max(...rows.map((r) => r.n));
  return (
    <ol className="adm-rank">
      {rows.map((r) => (
        <li key={r.label}>
          <span className="adm-rank-label">{r.label}</span>
          <span className="adm-rank-track" aria-hidden="true"><span style={{ width: `${(r.n / max) * 100}%` }} /></span>
          <b>{r.n.toLocaleString()}</b>
        </li>
      ))}
    </ol>
  );
}

function Ratings({ r }) {
  const { t } = useLanguage();
  if (!r) return <p className="adm-empty">{t('ยังไม่มีปุ่มให้คะแนนในระบบนี้ (มากับหน้าแชตแบบใหม่)', 'Rating buttons are not in this build yet (they come with the new chat page)')}</p>;
  const all = r.up + r.down;
  if (!all) return <p className="adm-empty">{t('ยังไม่มีใครให้คะแนน', 'No ratings yet')}</p>;
  return (
    <div className="adm-ratings">
      <p className="adm-big">{pct(r.up, all)}%<small>{t('ของคะแนนเป็น 👍', 'of ratings are 👍')}</small></p>
      <div className="adm-split" aria-hidden="true"><span className="s1" style={{ flexGrow: r.up }} /><span className="s2" style={{ flexGrow: r.down }} /></div>
      <ul className="adm-legend"><li><i className="s1" />👍 {t('ชอบ', 'Helpful')} {r.up}</li><li><i className="s2" />👎 {t('ไม่ชอบ', 'Not helpful')} {r.down}</li></ul>
    </div>
  );
}

function Status({ ok, label, on, off, neutral }) {
  const cls = ok ? 'is-good' : neutral ? 'is-info' : 'is-warn';
  return (
    <li>
      <span className={`adm-dot ${cls}`} aria-hidden="true" />
      <span>{label}</span>
      <b className={cls}>{ok ? <><Icon name="check" size={14} /> {on}</> : off}</b>
    </li>
  );
}

function Meter({ label, n, of }) {
  return (
    <div className="adm-meter">
      <div><span>{label}</span><b>{n}<small> / {of}</small></b></div>
      <div className="adm-meter-track" role="img" aria-label={`${label}: ${n} / ${of}`}><span style={{ width: `${pct(n, of)}%` }} /></div>
    </div>
  );
}
