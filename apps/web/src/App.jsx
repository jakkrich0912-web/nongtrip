import { NavLink, Route, Routes } from 'react-router-dom';
import Home from './pages/Home.jsx';
import Search from './pages/Search.jsx';
import Chat from './pages/Chat.jsx';
import Login from './pages/Login.jsx';
import Mascot from './components/Mascot.jsx';
import MascotHead from './components/MascotHead.jsx';

const Icon = ({ d }) => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
);
const NAV = [
  { to: '/', label: 'หน้าแรก', end: true, icon: <><path d="M3 11l9-7 9 7" /><path d="M5 10v10h14V10" /></> },
  { to: '/search', label: 'ค้นหา', icon: <><path d="M12 21s-7-6.2-7-11a7 7 0 0114 0c0 4.8-7 11-7 11z" /><circle cx="12" cy="10" r="2.5" /></> },
  { to: '/chat', label: 'แชตบอท', icon: <path d="M4 5h16v11H9l-5 4z" /> },
  { to: '/login', label: 'เข้าสู่ระบบ', icon: <><circle cx="12" cy="8" r="4" /><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6" /></> },
];

export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          <MascotHead size={46} className="brand-mark" />
          <span>น้องทริป<small>เที่ยวรอบที่พัก ทั่วไทย</small></span>
        </NavLink>
        <nav>
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end}>
              <Icon d={n.icon} /><span>{n.label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="side-card">
          <Mascot size={86} mood="wave" title="" />
          <p>ปักหมุดที่พักแล้ว น้องทริปจะหาที่เที่ยวรอบๆ ให้</p>
        </div>
      </header>
      <div className="content">
        <main>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/search" element={<Search />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/login" element={<Login />} />
          </Routes>
        </main>
        <footer className="foot">
          ระยะทางเป็นเส้นตรง ไม่ใช่ระยะขับรถ · ข้อมูลแผนที่ © OpenStreetMap contributors (ODbL)
        </footer>
      </div>
    </div>
  );
}
