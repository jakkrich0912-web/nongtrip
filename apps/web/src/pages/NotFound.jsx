import { Link, useLocation } from 'react-router-dom';
import Mascot from '../components/Mascot.jsx';
import { useLanguage } from '../lib/language.jsx';
import './info.css';

// ลิงก์ผิดหรือหน้าที่ไม่มี: บอกตรง ๆ แทนการเด้งไปหน้าแรกเงียบ ๆ
export default function NotFound() {
  const { t } = useLanguage();
  const { pathname } = useLocation();
  return (
    <div className="nti-404 nt-container">
      <Mascot size={150} mood="think" interactive={false} />
      <h1>{t('ไม่พบหน้านี้', 'Page not found')}</h1>
      <p>{t('น้องทริปหาหน้า ', 'NongTrip could not find ')}<code>{pathname}</code>{t(' ไม่เจอ ลิงก์อาจพิมพ์ผิด หรือหน้านี้ถูกย้ายไปแล้ว', '. The link may be mistyped, or the page has moved.')}</p>
      <div className="nti-404-links">
        <Link className="btn" to="/search">{t('ค้นหารอบที่พัก', 'Search around a stay')}</Link>
        <Link className="btn ghost" to="/provinces">{t('ดูทุกจังหวัด', 'Browse provinces')}</Link>
        <Link className="btn ghost" to="/">{t('กลับหน้าแรก', 'Back to home')}</Link>
      </div>
    </div>
  );
}
