// โหมดสว่าง/มืด: เก็บค่าที่เลือกในเบราว์เซอร์ ค่าเริ่มต้นเป็นสว่าง (index.html ตั้งค่าก่อนหน้าเว็บโหลด กันจอกระพริบ)
import { useEffect, useState } from 'react';

const KEY = 'nongtrip-theme';
export const THEMES = ['light', 'dark'];

export function readTheme(storage = globalThis.localStorage) {
  try {
    const v = storage?.getItem(KEY);
    return THEMES.includes(v) ? v : 'light';
  } catch {
    return 'light';
  }
}

export function applyTheme(theme, doc = globalThis.document, storage = globalThis.localStorage) {
  const value = THEMES.includes(theme) ? theme : 'light';
  if (doc?.documentElement) doc.documentElement.dataset.theme = value;
  try { storage?.setItem(KEY, value); } catch { /* ที่เก็บใช้ไม่ได้ ใช้ได้แค่หน้านี้ */ }
  return value;
}

export function useTheme() {
  const [theme, setTheme] = useState(readTheme);
  useEffect(() => { applyTheme(theme); }, [theme]);
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))];
}
