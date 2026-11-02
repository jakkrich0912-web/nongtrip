import { useState } from 'react';
import Rings from '../components/Rings.jsx';
import Mascot from '../components/Mascot.jsx';

// หน้าล็อกอิน: ฟอร์มพร้อม รอ endpoint ผู้ใช้จาก services/api
export default function Login() {
  const [mode, setMode] = useState('login');
  const [msg, setMsg] = useState('');
  const isLogin = mode === 'login';
  const submit = (e) => { e.preventDefault(); setMsg('ระบบบัญชียังไม่เปิดใช้ ระหว่างนี้ค้นและแชตได้โดยไม่ต้องเข้าสู่ระบบ'); };
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
        <form onSubmit={submit}>
          <label>อีเมล<input type="email" required autoComplete="email" /></label>
          <label>รหัสผ่าน<input type="password" required minLength={8} autoComplete={isLogin ? 'current-password' : 'new-password'} /></label>
          <button className="btn">{isLogin ? 'เข้าสู่ระบบ' : 'สร้างบัญชี'}</button>
        </form>
        {msg && <p className="note" role="status">{msg}</p>}
        <button className="linkbtn" onClick={() => { setMode(isLogin ? 'signup' : 'login'); setMsg(''); }}>
          {isLogin ? 'ยังไม่มีบัญชี สร้างบัญชี' : 'มีบัญชีแล้ว เข้าสู่ระบบ'}
        </button>
      </section>
    </div>
  );
}
