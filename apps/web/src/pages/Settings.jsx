import { useEffect, useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import { useAuth } from '../lib/auth.jsx';
import { changePassword, myAccount, revokeOtherSessions } from '../lib/api.js';
import { useLanguage } from '../lib/language.jsx';
import './info.css';

const MIN = 8;
const MAX = 200;

// ตรวจฟอร์มเปลี่ยนรหัสผ่านก่อนส่ง คืนข้อความผิดพลาด หรือ '' ถ้าผ่าน (หลังบ้านตรวจซ้ำอีกรอบเสมอ)
export function passwordFormError({ current, next, confirm }, t = (th) => th) {
  if (!current) return t('กรอกรหัสผ่านปัจจุบัน', 'Enter your current password');
  if (next.length < MIN || next.length > MAX) return t(`รหัสผ่านใหม่ต้องยาว ${MIN}-${MAX} ตัวอักษร`, `The new password must be ${MIN}-${MAX} characters`);
  if (next === current) return t('รหัสผ่านใหม่ต้องไม่ซ้ำกับรหัสผ่านเดิม', 'The new password must differ from the current one');
  if (next !== confirm) return t('ยืนยันรหัสผ่านใหม่ไม่ตรงกัน', 'The new passwords do not match');
  return '';
}

const fmtDate = (iso, lang) => {
  try { return new Date(iso).toLocaleDateString(lang === 'en' ? 'en-GB' : 'th-TH', { day: 'numeric', month: 'long', year: 'numeric' }); }
  catch { return ''; }
};

// หน้าตั้งค่าบัญชี: ข้อมูลบัญชี เปลี่ยนรหัสผ่าน ออกจากระบบอุปกรณ์อื่น (CONTRACT ข้อ 3.3)
export default function Settings() {
  const { user, ready } = useAuth();
  const { t } = useLanguage();
  if (!ready) return <p className="note" style={{ padding: 32 }} role="status">{t('กำลังโหลด', 'Loading…')}</p>;
  if (!user) return <Navigate to="/login" replace />;
  return <SettingsBody />;
}

function SettingsBody() {
  const { t, lang } = useLanguage();
  const { forget } = useAuth();
  const nav = useNavigate();
  const [acct, setAcct] = useState(null);
  const [error, setError] = useState('');
  const expire = () => { forget(); nav('/login', { replace: true, state: { expired: true } }); };
  const fail = (e, set) => (e.status === 401 ? expire() : set(e.message));
  const load = () => myAccount().then(setAcct).catch((e) => fail(e, setError));
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="mytrips">
      <nav className="nti-crumbs" aria-label={t('ตำแหน่งหน้า', 'Breadcrumb')}>
        <Link to="/me">{t('ทริปของฉัน', 'My trips')}</Link><span aria-hidden="true">›</span><span>{t('ตั้งค่าบัญชี', 'Account settings')}</span>
      </nav>
      <div className="mt-hero">
        <Mascot size={92} mood="front" interactive={false} />
        <div>
          <h1>{t('ตั้งค่าบัญชี', 'Account settings')}</h1>
          <p className="note">{acct?.email ?? ''}</p>
        </div>
      </div>
      {error && <p className="auth-error" role="alert">{error}</p>}
      {!acct && !error && <p className="note" role="status">{t('กำลังโหลด', 'Loading…')}</p>}
      {acct && (
        <div className="st-grid">
          <div className="st-col">
          <section className="mt-card st-card">
            <header><h2>{t('บัญชี', 'Account')}</h2></header>
            <dl className="st-facts">
              <dt>{t('อีเมล', 'Email')}</dt><dd>{acct.email}</dd>
              <dt>{t('สมัครเมื่อ', 'Joined')}</dt><dd>{fmtDate(acct.created_at, lang)}</dd>
              <dt>{t('เข้าสู่ระบบด้วย', 'Signs in with')}</dt><dd>{acct.google ? 'Google' : t('อีเมลและรหัสผ่าน', 'Email and password')}</dd>
              <dt>{t('อุปกรณ์ที่เข้าอยู่', 'Signed-in devices')}</dt><dd>{acct.sessions}</dd>
            </dl>
          </section>

          <DevicesCard acct={acct} onDone={load} onFail={fail} />

          <section className="mt-card st-card">
            <header><h2>{t('ข้อมูลและการลบบัญชี', 'Your data and account deletion')}</h2></header>
            <p>{t('ดูหรือลบที่พักที่ค้น สถานที่โปรด และประวัติแชต รวมถึงลบบัญชีถาวร ได้ที่หน้าทริปของฉัน', 'See or delete your searches, favourites and chats, or delete the account for good, on My trips.')}</p>
            <p><Link to="/me">{t('ไปที่ทริปของฉัน →', 'Go to My trips →')}</Link> · <Link to="/privacy">{t('เราเก็บข้อมูลอะไรบ้าง', 'What we store')}</Link></p>
          </section>
          </div>
          <div className="st-col"><PasswordCard acct={acct} onDone={load} onFail={fail} /></div>
        </div>
      )}
    </div>
  );
}

function PasswordCard({ acct, onDone, onFail }) {
  const { t } = useLanguage();
  const [form, setForm] = useState({ current: '', next: '', confirm: '' });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState({ ok: '', err: '' });
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  if (!acct.has_password) {
    return (
      <section className="mt-card st-card">
        <header><h2>{t('รหัสผ่าน', 'Password')}</h2></header>
        <p>{t('บัญชีนี้เข้าสู่ระบบด้วย Google จึงไม่มีรหัสผ่านในน้องทริป ความปลอดภัยของรหัสผ่านดูแลที่บัญชี Google ของคุณ', 'This account signs in with Google, so it has no NongTrip password. Your Google account looks after password security.')}</p>
      </section>
    );
  }

  const submit = async (e) => {
    e.preventDefault();
    const err = passwordFormError(form, t);
    if (err) { setMsg({ ok: '', err }); return; }
    setBusy(true);
    setMsg({ ok: '', err: '' });
    try {
      const d = await changePassword(form.current, form.next);
      setForm({ current: '', next: '', confirm: '' });
      const n = d?.signed_out ?? 0;
      setMsg({ ok: n > 0 ? t(`เปลี่ยนรหัสผ่านแล้ว และออกจากระบบอุปกรณ์อื่น ${n} เครื่อง`, `Password changed. ${n} other device(s) signed out.`) : t('เปลี่ยนรหัสผ่านแล้ว', 'Password changed.'), err: '' });
      onDone();
    } catch (ex) {
      onFail(ex, (m) => setMsg({ ok: '', err: m }));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mt-card st-card">
      <header><h2>{t('เปลี่ยนรหัสผ่าน', 'Change password')}</h2></header>
      <p>{t('เปลี่ยนแล้ว อุปกรณ์อื่นทั้งหมดจะถูกออกจากระบบ เครื่องนี้ยังเข้าอยู่', 'Every other device will be signed out. This one stays signed in.')}</p>
      <form className="st-form" onSubmit={submit} noValidate>
        <label>{t('รหัสผ่านปัจจุบัน', 'Current password')}<input type="password" autoComplete="current-password" value={form.current} onChange={set('current')} maxLength={MAX + 100} required /></label>
        <label>{t(`รหัสผ่านใหม่ (${MIN}-${MAX} ตัวอักษร)`, `New password (${MIN}-${MAX} characters)`)}<input type="password" autoComplete="new-password" value={form.next} onChange={set('next')} minLength={MIN} maxLength={MAX} required /></label>
        <label>{t('พิมพ์รหัสผ่านใหม่อีกครั้ง', 'Repeat the new password')}<input type="password" autoComplete="new-password" value={form.confirm} onChange={set('confirm')} maxLength={MAX} required /></label>
        {msg.err && <p className="auth-error" role="alert">{msg.err}</p>}
        {msg.ok && <p className="st-ok" role="status">{msg.ok}</p>}
        <button className="btn" disabled={busy}>{busy ? t('กำลังบันทึก', 'Saving…') : t('เปลี่ยนรหัสผ่าน', 'Change password')}</button>
      </form>
    </section>
  );
}

function DevicesCard({ acct, onDone, onFail }) {
  const { t } = useLanguage();
  const [ask, setAsk] = useState(false);
  const [msg, setMsg] = useState({ ok: '', err: '' });
  const others = Math.max(0, (acct.sessions ?? 1) - 1);
  const run = async () => {
    setAsk(false);
    try {
      const d = await revokeOtherSessions();
      setMsg({ ok: t(`ออกจากระบบอุปกรณ์อื่นแล้ว ${d?.signed_out ?? 0} เครื่อง`, `Signed out ${d?.signed_out ?? 0} other device(s).`), err: '' });
      onDone();
    } catch (ex) {
      onFail(ex, (m) => setMsg({ ok: '', err: m }));
    }
  };
  return (
    <section className="mt-card st-card">
      <header><h2>{t('อุปกรณ์ที่เข้าสู่ระบบ', 'Signed-in devices')}</h2></header>
      <p>{others > 0
        ? t(`มีอุปกรณ์อื่นเข้าบัญชีนี้อยู่ ${others} เครื่อง ถ้าจำไม่ได้ว่าเข้าจากที่ไหน ให้ออกจากระบบทั้งหมด แล้วเปลี่ยนรหัสผ่าน`, `${others} other device(s) are signed in. If you do not recognise them, sign them all out and change your password.`)
        : t('มีแค่เครื่องนี้ที่เข้าบัญชีอยู่', 'Only this device is signed in.')}</p>
      {msg.err && <p className="auth-error" role="alert">{msg.err}</p>}
      {msg.ok && <p className="st-ok" role="status">{msg.ok}</p>}
      {others > 0 && (ask
        ? <span className="confirm">
            <button className="linkbtn danger strong" onClick={run}>{t('ยืนยันออกจากระบบอุปกรณ์อื่น', 'Confirm sign-out')}</button>
            <button className="linkbtn" onClick={() => setAsk(false)}>{t('ยกเลิก', 'Cancel')}</button>
          </span>
        : <button className="btn ghost small" onClick={() => setAsk(true)}>{t('ออกจากระบบอุปกรณ์อื่นทั้งหมด', 'Sign out all other devices')}</button>)}
    </section>
  );
}
