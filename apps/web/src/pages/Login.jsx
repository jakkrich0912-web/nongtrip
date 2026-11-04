import { useEffect, useRef, useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import MascotHead from '../components/MascotHead.jsx';
import MascotStage from '../components/MascotStage.jsx';
import AuthScene from '../components/AuthScene.jsx';
import { useAuth } from '../lib/auth.jsx';
import { useLanguage } from '../lib/language.jsx';
import '../auth-v2.css';

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID?.trim();
let googleScript;
let googleInitialized = false;
let googleCredentialHandler;

function loadGoogleIdentity() {
  if (window.google?.accounts?.id) return Promise.resolve(window.google.accounts.id);
  if (!googleScript) {
    googleScript = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://accounts.google.com/gsi/client';
      script.async = true;
      script.onload = () => window.google?.accounts?.id
        ? resolve(window.google.accounts.id)
        : reject(new Error('google_unavailable'));
      script.onerror = () => { script.remove(); reject(new Error('google_unavailable')); };
      document.head.appendChild(script);
    }).catch((error) => { googleScript = undefined; throw error; });
  }
  return googleScript;
}

function Arrow({ back = false }) {
  return <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d={back ? 'M19 12H5m6-6-6 6 6 6' : 'M5 12h14m-6-6 6 6-6 6'} /></svg>;
}

export default function Login({ mode = 'login' }) {
  const { user, ready, login, register, googleLogin } = useAuth();
  const { lang, t, setLang } = useLanguage();
  const navigate = useNavigate();
  const expired = useLocation().state?.expired === true;
  const isLogin = mode === 'login';
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [googleState, setGoogleState] = useState(GOOGLE_CLIENT_ID ? 'loading' : 'disabled');
  const googleButton = useRef(null);
  const credentialCallback = useRef(null);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  // ท่าทางของน้องทริปตามที่ผู้ใช้ทำในฟอร์ม (MascotStage) at ทำให้ cue ชื่อเดิมเล่นซ้ำได้
  const [cue, setCue] = useState(null);
  const say = (name, extra = {}) => setCue({ name, at: Date.now(), ...extra });
  const prevLogin = useRef(isLogin);
  // สลับหน้าเข้าสู่ระบบ/สมัคร: หน้าเดิม (ไม่โหลดใหม่) แผงเลื่อนข้ามกัน น้องทริปวิ่งตามไปฝั่งใหม่ ล้างข้อความผิดพลาดเก่า
  useEffect(() => {
    if (prevLogin.current === isLogin) return;
    prevLogin.current = isLogin;
    setError('');
    say('travel', { dir: isLogin ? -1 : 1 });
  }, [isLogin]);
  useEffect(() => { if (error) say('error'); }, [error]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const authenticate = async (action) => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    try {
      await action();
      if (mounted.current) navigate('/me');
    } catch (err) {
      if (mounted.current) setError(err.message);
    } finally {
      inFlight.current = false;
      if (mounted.current) setBusy(false);
    }
  };
  credentialCallback.current = (response) => {
    if (response.credential && mounted.current) authenticate(() => googleLogin(response.credential));
  };

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID || user) return undefined;
    let cancelled = false;
    const handler = (response) => credentialCallback.current?.(response);
    setGoogleState('loading');
    loadGoogleIdentity().then((identity) => {
      if (cancelled || !googleButton.current) return;
      googleCredentialHandler = handler;
      if (!googleInitialized) {
        identity.initialize({
          client_id: GOOGLE_CLIENT_ID,
          callback: (response) => googleCredentialHandler?.(response),
          auto_select: false,
        });
        googleInitialized = true;
      }
      googleButton.current.replaceChildren();
      identity.renderButton(googleButton.current, {
        type: 'standard', theme: 'outline', size: 'large', shape: 'pill',
        text: isLogin ? 'signin_with' : 'signup_with', locale: lang,
        width: Math.min(400, googleButton.current.clientWidth || 300),
      });
      setGoogleState('ready');
    }).catch(() => { if (!cancelled) setGoogleState('error'); });
    return () => {
      cancelled = true;
      if (googleCredentialHandler === handler) googleCredentialHandler = undefined;
    };
  }, [lang, isLogin, user]);

  if (ready && user) return <Navigate to="/me" replace />;

  // ข้อความในกล่องพูดของน้องทริป เปลี่ยนตามสิ่งที่ผู้ใช้กำลังทำ
  const SPEECH = {
    email: t('พิมพ์อีเมลได้เลย เดี๋ยวน้องจำไว้ให้', 'Type your email, I’ll remember it'),
    password: t('ไม่แอบดูนะ ปิดตาแล้ว', 'I’m not peeking, promise'),
    reveal: t('เอ๊ะ เห็นรหัสแล้วนะ', 'Oops, I can see it now'),
    error: t('อุ๊ย ลองใหม่อีกทีนะ', 'Oops, let’s try that again'),
    travel: isLogin ? t('กลับมาแล้ว! ไปเที่ยวต่อกัน', 'Welcome back! Let’s go') : t('ไปเริ่มทริปแรกกัน!', 'Off to your first trip!'),
  };
  const speech = (cue && SPEECH[cue.name]) || (isLogin ? t('พร้อมออกไปสำรวจกันหรือยัง?', 'Ready for a little adventure?') : t('มาเริ่มทริปแรกด้วยกันนะ!', 'Let’s start your first trip!'));
  const parallax = (e) => {
    const b = e.currentTarget.getBoundingClientRect();
    e.currentTarget.style.setProperty('--px', (((e.clientX - b.left) / b.width) * 2 - 1).toFixed(3));
    e.currentTarget.style.setProperty('--py', (((e.clientY - b.top) / b.height) * 2 - 1).toFixed(3));
  };
  const onPasswordFocus = () => say(showPassword ? 'reveal' : 'password');

  const submit = (event) => {
    event.preventDefault();
    authenticate(() => (isLogin ? login : register)(email.trim(), password));
  };

  return (
    <div className={`nt-auth-page ${isLogin ? 'is-login' : 'is-signup'}`}>
      <aside className="nt-auth-story" aria-label={t('เพื่อนร่วมทางของคุณ', 'Your travel companion')} onPointerMove={parallax}>
        <AuthScene variant={isLogin ? 'day' : 'dusk'} />
        <Link to="/" className="nt-auth-brand"><MascotHead size={46} /><span>{t('น้องทริป', 'NongTrip')}<small>YOUR LITTLE TRAVEL BUDDY</small></span></Link>
        <div className="nt-auth-story-copy">
          <span className="nt-auth-eyebrow">{isLogin ? 'A LITTLE CURIOSITY. A NEW JOURNEY.' : 'EVERY JOURNEY STARTS WITH A PIN.'}</span>
          <h2 key={isLogin ? 'in' : 'up'}>{isLogin ? t('ทุกทริปมีเรื่องให้ค้นพบ', 'Every trip has a story.') : t('ปักหมุดที่พักแรก', 'Drop your first pin.')}<br /><span>{isLogin ? t('ไปด้วยกันนะ', 'Let’s find yours.') : t('แล้วออกไปเที่ยวกัน', 'Then go explore.')}</span></h2>
          <p>{isLogin ? t('บันทึกที่พัก เก็บสถานที่ที่ถูกใจ แล้วกลับมาวางแผนทริปครั้งต่อไปด้วยกัน', 'Save your stays and favourite places. Come back whenever your next adventure calls.') : t('สมัครแล้วเก็บที่พักที่ค้น สถานที่โปรด และประวัติแชตไว้ดูต่อได้ทุกเครื่อง', 'Sign up to keep your stays, favourite places and chats on every device.')}</p>
        </div>
        <div className="nt-auth-mascot-scene">
          <span className="nt-auth-live" aria-live="polite">{speech}</span>
          <MascotStage size={250} cue={cue} formSide={isLogin ? 'right' : 'left'} title={t('น้องทริป แมวส้มนักสำรวจ', 'NongTrip, the orange explorer cat')}>
            <span className="nt-auth-speech" key={speech} aria-hidden="true">{speech}</span>
          </MascotStage>
        </div>
        <p className="nt-auth-story-foot">{t('เริ่มจากที่พัก แล้วออกไปเจอสิ่งใหม่ ๆ', 'Start with your stay. Discover what’s around.')}</p>
      </aside>

      <section className="nt-auth-form-panel">
        <div className="nt-auth-topline">
          <Link to="/" className="nt-auth-back"><Arrow back />{t('กลับหน้าแรก', 'Back home')}</Link>
          <div className="nt-auth-languages" aria-label={t('เลือกภาษา', 'Language')}>
            <button type="button" lang="th" aria-pressed={lang === 'th'} onClick={() => setLang('th')}>TH</button><span aria-hidden="true">/</span><button type="button" lang="en" aria-pressed={lang === 'en'} onClick={() => setLang('en')}>EN</button>
          </div>
        </div>
        <div className="nt-auth-form-content">
          <span className="nt-auth-kicker">{t('เพื่อนร่วมทางคนเดิม รออยู่ตรงนี้', 'YOUR NEXT JOURNEY STARTS HERE')}</span>
          <h1>{isLogin ? t('ยินดีที่ได้เจอกันอีก', 'Welcome back.') : t('เริ่มต้นทริปของคุณ', 'Make room for adventure.')}</h1>
          <p className="nt-auth-intro">{isLogin ? t('เข้าสู่ระบบ แล้วมาค้นพบสถานที่รอบที่พักด้วยกัน', 'Sign in to keep exploring the places around your stay.') : t('สร้างบัญชีเพื่อเก็บสถานที่ที่ถูกใจและประวัติทริป', 'Create an account to save your favourite places and trip history.')}</p>

          <div className="nt-auth-google-area" aria-busy={googleState === 'loading' || busy}>
            {GOOGLE_CLIENT_ID && <div className={`nt-auth-google-button${busy ? ' nt-auth-google-busy' : ''}`} ref={googleButton} inert={busy ? '' : undefined} />}
            {googleState !== 'ready' && <button className="nt-auth-google-placeholder" type="button" disabled aria-describedby="nt-auth-google-note"><span aria-hidden="true">G</span>{t('ดำเนินการต่อด้วย Google', 'Continue with Google')}</button>}
            {googleState !== 'ready' && <p id="nt-auth-google-note" className="nt-auth-small" role="status">{googleState === 'disabled' ? t('การเข้าสู่ระบบด้วย Google ยังไม่เปิดให้บริการ', 'Google sign-in is not available yet.') : googleState === 'error' ? t('เชื่อมต่อ Google ไม่ได้ ใช้อีเมลเข้าสู่ระบบได้เลย', 'Google could not load. You can sign in with email.') : t('กำลังเชื่อมต่อ Google…', 'Connecting to Google…')}</p>}
          </div>

          <div className="nt-auth-divider"><span>{t('หรือใช้อีเมล', 'or continue with email')}</span></div>
          {expired && !error && <p className="nt-auth-message" role="status">{t('หมดเวลาเข้าสู่ระบบ กรุณาเข้าสู่ระบบอีกครั้ง', 'Your session expired. Please sign in again.')}</p>}
          <form className="nt-auth-form" onSubmit={submit} aria-busy={busy}>
            <label htmlFor="nt-auth-email">{t('อีเมล', 'Email address')}</label>
            <input id="nt-auth-email" type="email" required autoComplete="email" placeholder="you@example.com" value={email} onChange={(event) => { setEmail(event.target.value); if (cue?.name !== 'email' || Date.now() - cue.at > 900) say('email'); }} onFocus={() => say('email')} disabled={busy} />
            <label htmlFor="nt-auth-password">{t('รหัสผ่าน', 'Password')}</label>
            <div className="nt-auth-password-field">
              <input id="nt-auth-password" type={showPassword ? 'text' : 'password'} required minLength={8} maxLength={200} autoComplete={isLogin ? 'current-password' : 'new-password'} placeholder={t('อย่างน้อย 8 ตัวอักษร', 'At least 8 characters')} value={password} onChange={(event) => setPassword(event.target.value)} onFocus={onPasswordFocus} onBlur={() => setCue(null)} aria-describedby={!isLogin ? 'nt-auth-password-hint' : undefined} disabled={busy} />
              <button type="button" className="nt-auth-password-toggle" onClick={() => { setShowPassword(!showPassword); say(showPassword ? 'password' : 'reveal'); }} aria-label={showPassword ? t('ซ่อนรหัสผ่าน', 'Hide password') : t('แสดงรหัสผ่าน', 'Show password')} aria-pressed={showPassword}>
                <svg aria-hidden="true" width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6"><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12Z" /><circle cx="12" cy="12" r="3" />{showPassword && <path d="m3 3 18 18" />}</svg>
              </button>
            </div>
            {!isLogin && <p id="nt-auth-password-hint" className="nt-auth-small">{t('ใช้รหัสผ่าน 8–200 ตัวอักษร', 'Use a password between 8 and 200 characters.')}</p>}
            {!isLogin && <p className="nt-auth-small">{t('เราเก็บแค่อีเมล ประวัติค้น สถานที่โปรด และแชตของคุณ ลบเองได้ทุกเมื่อ ', 'We keep only your email, searches, favourites and chats, and you can delete them any time. ')}<Link to="/privacy">{t('อ่านรายละเอียด', 'Read the details')}</Link></p>}
            {error && <p className="nt-auth-error" role="alert">{error}</p>}
            <button className="nt-auth-submit" type="submit" data-mascot-cheer disabled={busy}>{busy ? t('กำลังดำเนินการ…', 'Please wait…') : isLogin ? t('เข้าสู่ระบบ', 'Sign in') : t('สร้างบัญชี', 'Create account')}<Arrow /></button>
          </form>
          <p className="nt-auth-switch">{isLogin ? t('ยังไม่มีบัญชี?', 'New here?') : t('มีบัญชีแล้ว?', 'Already have an account?')} <Link to={isLogin ? '/signup' : '/login'}>{isLogin ? t('สมัครใช้งาน', 'Create an account') : t('เข้าสู่ระบบ', 'Sign in')}</Link></p>
          <div className="nt-auth-guest"><span aria-hidden="true">↗</span><p>{t('อยากลองดูก่อน?', 'Just looking around?')} <Link to="/search">{t('ค้นหาโดยไม่ต้องเข้าสู่ระบบ', 'Explore without an account')}</Link><small>{t('ค้นหาและแชตได้ แต่จะไม่บันทึกประวัติ', 'Search and chat without saving your history.')}</small></p></div>
        </div>
        <p className="nt-auth-form-foot">{t('น้องทริป · เพื่อนตัวเล็กของทุกการเดินทาง', 'NongTrip · A little friend for every journey')}</p>
      </section>
    </div>
  );
}
