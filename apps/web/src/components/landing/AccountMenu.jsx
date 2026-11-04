import { useEffect, useId, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../lib/auth.jsx';
import { useLanguage } from '../../lib/language.jsx';
import Icon from './Icon.jsx';

// ตัวอักษรบนรูปโปรไฟล์: ตัวแรกของอีเมล (ตัวพิมพ์ใหญ่) ไม่มีอีเมลใช้ ?
export const initialOf = (email) => (Array.from((email ?? '').trim())[0] ?? '?').toUpperCase();

// ปุ่มรูปโปรไฟล์ที่หัวเว็บ (เฉพาะผู้ที่ล็อกอิน) กดแล้วเปิดเมนูบัญชี
// ปิดเมนูเมื่อกดข้างนอก กด Esc เปลี่ยนหน้า หรือเลือกรายการ ใช้ลูกศรขึ้นลงเลื่อนระหว่างรายการได้
export default function AccountMenu() {
  const { user, logout } = useAuth();
  const { t } = useLanguage();
  const nav = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const button = useRef(null);
  const menuId = useId();

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e) => { if (!root.current?.contains(e.target)) setOpen(false); };
    const onKey = (e) => { if (e.key === 'Escape') { setOpen(false); button.current?.focus(); } };
    document.addEventListener('pointerdown', onDown);
    document.addEventListener('keydown', onKey);
    return () => { document.removeEventListener('pointerdown', onDown); document.removeEventListener('keydown', onKey); };
  }, [open]);

  const items = () => Array.from(root.current?.querySelectorAll('[role="menuitem"]') ?? []);
  const openWith = (focus) => { setOpen(true); requestAnimationFrame(() => { const xs = items(); (focus === 'last' ? xs.at(-1) : xs[0])?.focus(); }); };
  const close = (refocus = true) => { setOpen(false); if (refocus) button.current?.focus(); };

  const onButtonKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); openWith('first'); }
    if (e.key === 'ArrowUp') { e.preventDefault(); openWith('last'); }
  };
  const onMenuKey = (e) => {
    const xs = items();
    const i = xs.indexOf(document.activeElement);
    if (e.key === 'ArrowDown') { e.preventDefault(); xs[(i + 1) % xs.length]?.focus(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); xs[(i - 1 + xs.length) % xs.length]?.focus(); }
    else if (e.key === 'Home') { e.preventDefault(); xs[0]?.focus(); }
    else if (e.key === 'End') { e.preventDefault(); xs.at(-1)?.focus(); }
    else if (e.key === 'Tab') setOpen(false);
  };

  if (!user) return null;
  const links = [
    ['/me', 'pin', t('ทริปของฉัน', 'My trips'), t('ที่พักที่ค้น สถานที่โปรด', 'Searches and favourites')],
    ['/chat', 'chat', t('แชตของฉัน', 'My chats'), t('คุยต่อจากแชตเดิม', 'Pick up a conversation')],
    ['/settings', 'settings', t('ตั้งค่าบัญชี', 'Account settings'), t('รหัสผ่าน อุปกรณ์ที่เข้าอยู่', 'Password and devices')],
  ];

  return (
    <div className="nt-account" ref={root}>
      <button ref={button} type="button" className="nt-account-btn" aria-haspopup="menu" aria-expanded={open} aria-controls={menuId}
        aria-label={t(`เมนูบัญชี ${user.email}`, `Account menu for ${user.email}`)}
        onClick={() => (open ? close(false) : setOpen(true))} onKeyDown={onButtonKey}>
        <span className="nt-avatar" aria-hidden="true">{initialOf(user.email)}</span>
        <Icon name="chevron" size={15} className="nt-account-caret" />
      </button>
      {open && (
        <div id={menuId} className="nt-account-menu" role="menu" aria-label={t('บัญชีของฉัน', 'My account')} onKeyDown={onMenuKey}>
          <div className="nt-account-head">
            <span className="nt-avatar nt-avatar-lg" aria-hidden="true">{initialOf(user.email)}</span>
            <div><small>{t('เข้าสู่ระบบในชื่อ', 'Signed in as')}</small><strong title={user.email}>{user.email}</strong></div>
          </div>
          <div className="nt-account-group">
            {links.map(([to, icon, label, hint]) => (
              <Link key={to} to={to} role="menuitem" className={pathname === to ? 'is-current' : ''} aria-current={pathname === to ? 'page' : undefined} onClick={() => setOpen(false)}>
                <Icon name={icon} size={18} /><span>{label}<small>{hint}</small></span>
              </Link>
            ))}
          </div>
          <div className="nt-account-group">
            <Link to="/privacy" role="menuitem" onClick={() => setOpen(false)}><Icon name="shield" size={18} /><span>{t('ความเป็นส่วนตัว', 'Privacy')}</span></Link>
            <button type="button" role="menuitem" className="nt-account-logout" onClick={async () => { setOpen(false); await logout(); nav('/'); }}>
              <Icon name="logout" size={18} /><span>{t('ออกจากระบบ', 'Log out')}</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
