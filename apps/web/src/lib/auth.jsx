import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { authLogin, authLogout, authMe, authRegister, myFavorites } from './api.js';

// สถานะผู้ใช้ทั้งเว็บ: ใครล็อกอินอยู่ และรหัสสถานที่โปรด (ใช้แสดงหัวใจบนการ์ด)
// ผู้ที่ไม่ล็อกอิน user = null และหน้าเว็บซ่อนปุ่มบันทึกทั้งหมด (ข้อ 3.3)
const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);
  const [favIds, setFavIds] = useState(() => new Set());

  const loadFavs = useCallback(() => myFavorites()
    .then((d) => setFavIds(new Set(d.items.map((i) => i.id))))
    .catch(() => setFavIds(new Set())), []);

  useEffect(() => {
    authMe()
      .then((d) => { setUser(d.user); loadFavs(); })
      .catch(() => setUser(null))
      .finally(() => setReady(true));
  }, [loadFavs]);

  const login = async (email, password) => { const d = await authLogin(email, password); setUser(d.user); loadFavs(); return d.user; };
  const register = async (email, password) => { const d = await authRegister(email, password); setUser(d.user); setFavIds(new Set()); return d.user; };
  const logout = async () => { try { await authLogout(); } finally { setUser(null); setFavIds(new Set()); } };
  const forget = () => { setUser(null); setFavIds(new Set()); };

  return (
    <AuthContext.Provider value={{ user, ready, login, register, logout, forget, favIds, setFavIds, loadFavs }}>
      {children}
    </AuthContext.Provider>
  );
}

export const useAuth = () => useContext(AuthContext);
