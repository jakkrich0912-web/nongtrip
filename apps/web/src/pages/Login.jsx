import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import Rings from '../components/Rings.jsx';
import Mascot from '../components/Mascot.jsx';
import { useAuth } from '../lib/auth.jsx';

// เข้าสู่ระบบและสมัครด้วยอีเมล POST /api/auth/login, /api/auth/register (ข้อ 3.3)
// ข้อความผิดพลาดใช้ฟิลด์ error จาก API ตรงๆ
export default function Login() {
  const { user, ready, login, register } = useAuth();
  const nav = useNavigate();
  const expired = useLocation().state?.expired === true;
  const [mode, setMode] = useState('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const isLogin = mode === 'login';

  if (ready && user) return <Navigate to="/me" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setError('');
    try {
      await (isLogin ? login : register)(email.trim(), password);
      nav('/me');
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };
  const switchMode = () => { setMode(isLogin ? 'signup' : 'login'); setError(''); };

  return (
    <div className="auth-wrap">
      <div className="auth-side">
        <Rings pins={false} />
        <Mascot size={150} mood="front" className="login-buddy" />
        <h3>เก็บทริปไว้กลับมาดูทีหลัง</h3>
        <p>เข้าสู่ระบบเพื่อบันทึกที่พักที่เคยค้น สถานที่โปรด และประวัติแชต</p>
      </div>
      <section className="auth">
        <h2>{isLogin ? 'เข้าสู่ระบบ' : 'สร้างบัญชี'}</h2>
        {expired && !error && <p className="notice" role="status">หมดเวลาเข้าสู่ระบบ กรุณาเข้าสู่ระบบอีกครั้ง</p>}
        <form onSubmit={submit} noValidate={false}>
          <label>อีเมล
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>รหัสผ่าน
            <input
              type="password" required minLength={8} maxLength={200}
              autoComplete={isLogin ? 'current-password' : 'new-password'}
              value={password} onChange={(e) => setPassword(e.target.value)}
              aria-describedby={isLogin ? undefined : 'pw-hint'}
            />
          </label>
          {!isLogin && <p id="pw-hint" className="note">อย่างน้อย 8 ตัวอักษร</p>}
          {error && <p className="auth-error" role="alert">{error}</p>}
          <button className="btn" disabled={busy}>
            {busy ? 'กำลังดำเนินการ' : isLogin ? 'เข้าสู่ระบบ' : 'สร้างบัญชี'}
          </button>
        </form>
        <button className="linkbtn" onClick={switchMode}>
          {isLogin ? 'ยังไม่มีบัญชี สร้างบัญชี' : 'มีบัญชีแล้ว เข้าสู่ระบบ'}
        </button>
        <p className="note">ไม่เข้าสู่ระบบก็ค้นและแชตได้ แต่ระบบจะไม่บันทึกอะไรไว้เลย <Link to="/search">ไปค้นหาเลย</Link></p>
      </section>
    </div>
  );
}
