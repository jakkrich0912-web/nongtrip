import { useAuth } from '../lib/auth.jsx';
import { addFavorite, removeFavorite } from '../lib/api.js';
import { useLanguage } from '../lib/language.jsx';

// ปุ่มหัวใจสถานที่โปรด แสดงเฉพาะเมื่อล็อกอิน (ไม่ล็อกอินไม่บันทึกอะไร)
// อัปเดตหน้าจอก่อน ถ้าบันทึกไม่ผ่านคืนค่าเดิมและส่งข้อความผ่าน onError
export default function FavButton({ place, onError, className = '' }) {
  const { user, favIds, setFavIds, forget } = useAuth();
  const { t } = useLanguage();
  if (!user || !place) return null;
  const on = favIds.has(place.id);
  const toggle = (e) => {
    e.preventDefault(); e.stopPropagation();
    const before = favIds;
    const next = new Set(favIds); on ? next.delete(place.id) : next.add(place.id); setFavIds(next);
    onError?.('');
    (on ? removeFavorite(place.id) : addFavorite(place)).catch((err) => {
      setFavIds(before);
      // session หมดอายุ: ซ่อนปุ่มบันทึกทั้งเว็บ และบอกให้เข้าสู่ระบบใหม่ (รีวิว PR #17)
      if (err.status === 401) { forget(); onError?.(t('หมดเวลาเข้าสู่ระบบ กรุณาเข้าสู่ระบบอีกครั้งเพื่อบันทึก', 'Your session expired. Please log in again to save.')); }
      else onError?.(err.message);
    });
  };
  return (
    <button
      className={`fav ${on ? 'on' : ''} ${className}`}
      aria-pressed={on}
      aria-label={on ? t(`เอา ${place.name_th} ออกจากสถานที่โปรด`, `Remove ${place.name_th} from favourites`) : t(`เก็บ ${place.name_th} เป็นสถานที่โปรด`, `Save ${place.name_th} as a favourite`)}
      onClick={toggle}
    >
      <svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M12 20s-7-4.4-7-10a4 4 0 017-2.6A4 4 0 0119 10c0 5.6-7 10-7 10z" /></svg>
    </button>
  );
}
