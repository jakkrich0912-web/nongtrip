import { useState } from 'react';
import { Link, NavLink } from 'react-router-dom';
import { useLanguage } from '../../lib/language.jsx';
import { useAuth } from '../../lib/auth.jsx';
import head from '../../assets/mascot/head.webp';
import Icon from './Icon.jsx';
import { useTheme } from '../../lib/theme.js';
import AccountMenu from './AccountMenu.jsx';

export function LanguageSwitch() {
  const { lang, setLang, t } = useLanguage();
  return <div className="nt-language" role="group" aria-label={t('ภาษา', 'Language')}>
    {['th', 'en'].map(value => <button key={value} type="button" aria-pressed={lang === value} onClick={() => setLang(value)}>{value.toUpperCase()}</button>)}
  </div>;
}
export function ThemeSwitch() {
  const { t } = useLanguage();
  const [theme, toggle] = useTheme();
  const dark = theme === 'dark';
  return <button type="button" className="nt-theme" onClick={toggle} aria-pressed={dark}
    aria-label={dark ? t('ใช้โหมดสว่าง', 'Use light mode') : t('ใช้โหมดมืด', 'Use dark mode')} title={dark ? t('โหมดสว่าง', 'Light mode') : t('โหมดมืด', 'Dark mode')}>
    <span aria-hidden="true">{dark ? '☀' : '☾'}</span>
  </button>;
}
export function Brand() {
  const { t } = useLanguage();
  return <Link to="/" className="nt-brand"><img src={head} alt="" /><span>{t('น้องทริป', 'NongTrip')}<small>YOUR LITTLE TRAVEL BUDDY</small></span></Link>;
}
export default function SiteHeader() {
  const { t } = useLanguage();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  return <header className="nt-header"><div className="nt-header-inner">
    <Brand />
    <nav id="nt-navigation" className={open ? 'is-open' : ''} aria-label={t('เมนูหลัก', 'Main navigation')} onClick={() => setOpen(false)}>
      <NavLink to="/" end>{t('หน้าแรก', 'Home')}</NavLink>
      <NavLink to="/search">{t('ค้นหารอบที่พัก', 'Search')}</NavLink>
      <NavLink to="/provinces">{t('ทุกจังหวัด', 'Provinces')}</NavLink>
      <NavLink to="/chat">{t('คุยกับน้องทริป', 'Chat')}</NavLink>
      <a href="/#how-it-works">{t('ใช้งานอย่างไร', 'How it works')}</a>
      {!user && <Link className="nt-mobile-account" to="/login">{t('เข้าสู่ระบบ', 'Log in')}</Link>}
    </nav>
    <div className="nt-header-actions"><ThemeSwitch /><LanguageSwitch />{user ? <AccountMenu /> : <Link className="nt-login-link" to="/login">{t('เข้าสู่ระบบ', 'Log in')}<Icon size={17} /></Link>}<button className="nt-menu" type="button" aria-label={t('เปิดเมนู', 'Toggle menu')} aria-expanded={open} aria-controls="nt-navigation" onClick={() => setOpen(!open)}><Icon name="menu" /></button></div>
  </div></header>;
}

