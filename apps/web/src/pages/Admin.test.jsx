import { describe, expect, it } from 'vitest';
import { niceMax, pct, shortDay } from './Admin.jsx';
import menuSource from '../components/landing/AccountMenu.jsx?raw';
import appSource from '../App.jsx?raw';

describe('admin dashboard helpers', () => {
  it('rounds the y-axis up to a friendly number', () => {
    expect(niceMax(0)).toBe(4);
    expect(niceMax(3)).toBe(4);
    expect(niceMax(7)).toBe(8);
    expect(niceMax(13)).toBe(20);
    expect(niceMax(23)).toBe(40);
    expect(niceMax(140)).toBe(200);
    for (const v of [0, 5, 9, 31, 77, 512]) expect(niceMax(v) / 2 % 1).toBe(0);
  });
  it('percent never divides by zero', () => {
    expect(pct(1, 3)).toBe(33);
    expect(pct(5, 0)).toBe(0);
  });
  it('formats a UTC day without shifting it', () => {
    expect(shortDay('2026-11-04', 'en')).toBe('4 Nov');
  });
  it('is routed and only linked for administrators', () => {
    expect(appSource).toContain('<Route path="/admin" element={<Admin />} />');
    expect(menuSource).toContain("user.is_admin ? [['/admin'");
  });
});
