import { createContext, useContext, useEffect, useState } from 'react';

const LanguageContext = createContext(null);
export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    try { return localStorage.getItem('nongtrip-language') === 'en' ? 'en' : 'th'; }
    catch { return 'th'; }
  });
  useEffect(() => {
    document.documentElement.lang = lang;
    try { localStorage.setItem('nongtrip-language', lang); } catch { /* Storage is optional. */ }
  }, [lang]);
  return <LanguageContext.Provider value={{ lang, setLang, t: (th, en) => lang === 'en' ? en : th }}>{children}</LanguageContext.Provider>;
}
export const useLanguage = () => useContext(LanguageContext);
