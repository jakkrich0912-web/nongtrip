import { useEffect } from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import Home from './pages/Home.jsx';
import Search from './pages/Search.jsx';
import Chat from './pages/Chat.jsx';
import Login from './pages/Login.jsx';
import MyTrips from './pages/MyTrips.jsx';
import PlaceDetail from './pages/PlaceDetail.jsx';
import ProvincePage from './pages/ProvincePage.jsx';
import Provinces from './pages/Provinces.jsx';
import About from './pages/About.jsx';
import Privacy from './pages/Privacy.jsx';
import Settings from './pages/Settings.jsx';
import NotFound from './pages/NotFound.jsx';
import { Link } from 'react-router-dom';
import SiteHeader, { Brand } from './components/landing/SiteHeader.jsx';
import ChatCompanion from './components/ChatCompanion.jsx';
import { CompanionHintProvider } from './lib/companionContext.jsx';
import { useLanguage } from './lib/language.jsx';
import './landing.css';

export default function App() {
  const { pathname, hash } = useLocation();
  const { t } = useLanguage();
  useEffect(() => { if (!hash) window.scrollTo(0, 0); }, [pathname]);
  const auth = pathname === '/login' || pathname === '/signup';
  return <CompanionHintProvider><div className={`nt-app ${auth ? 'nt-auth-route' : ''}`}>
    {!auth && <><a className="nt-skip" href="#main-content">{t('ข้ามไปเนื้อหา', 'Skip to content')}</a><SiteHeader /></>}
    <main id="main-content" className={pathname === '/' || auth ? '' : 'nt-workspace'}>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/search" element={<Search />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/login" element={<Login key="login" mode="login" />} />
        <Route path="/signup" element={<Login key="signup" mode="signup" />} />
        <Route path="/me" element={<MyTrips />} />
        <Route path="/places/:id" element={<PlaceDetail />} />
        <Route path="/settings" element={<Settings />} />
        <Route path="/provinces" element={<Provinces />} />
        <Route path="/provinces/:name" element={<ProvincePage />} />
        <Route path="/about" element={<About />} />
        <Route path="/privacy" element={<Privacy />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </main>
    {!auth && <footer className="nt-footer nt-container"><div><Brand /><p>{t('โครงงานมหาวิทยาลัยเทคโนโลยีราชมงคลธัญบุรี', 'A project by Rajamangala University of Technology Thanyaburi')}</p></div><nav className="nt-footer-links" aria-label={t('ลิงก์ส่วนท้าย', 'Footer links')}><Link to="/about">{t('เกี่ยวกับเรา', 'About')}</Link><Link to="/provinces">{t('ทุกจังหวัด', 'All provinces')}</Link><Link to="/privacy">{t('ความเป็นส่วนตัว', 'Privacy')}</Link></nav><div><p>{t('ระยะทางเป็นเส้นตรง ไม่ใช่ระยะขับรถ', 'Distances are straight-line, not driving distances.')}</p><a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">Map data © OpenStreetMap contributors (ODbL)</a></div></footer>}
    <ChatCompanion hidden={auth || pathname === '/chat'} />
  </div></CompanionHintProvider>;
}
