import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi } from 'vitest';
import { LanguageProvider } from '../lib/language.jsx';
import { AuthProvider } from '../lib/auth.jsx';
import Privacy from './Privacy.jsx';
import About, { coverageOf } from './About.jsx';
import Provinces, { filterRegions } from './Provinces.jsx';
import NotFound from './NotFound.jsx';
import { passwordFormError } from './Settings.jsx';
import appSource from '../App.jsx?raw';

vi.mock('../lib/api.js', async (orig) => ({ ...(await orig()), systemHealth: () => new Promise(() => {}), provincesList: () => new Promise(() => {}), authMe: () => new Promise(() => {}) }));

const render = (node, path = '/') => renderToStaticMarkup(
  <MemoryRouter initialEntries={[path]}><LanguageProvider><AuthProvider>{node}</AuthProvider></LanguageProvider></MemoryRouter>,
);

describe('privacy page', () => {
  const html = render(<Privacy />);
  it('has every section its table of contents links to', () => {
    for (const id of ['summary', 'stored', 'outside', 'device', 'logs', 'control', 'security', 'contact']) {
      expect(html).toContain(`href="#${id}"`);
      expect(html).toContain(`id="${id}"`);
    }
  });
  it('names the real cookie, hashing and where to delete data', () => {
    expect(html).toContain('nt_session');
    expect(html).toContain('scrypt');
    expect(html).toContain('href="/me"');
    expect(html).toContain('href="/settings"');
    expect(html).toContain('tile.openstreetmap.org');
  });
  it('does not claim the chat mode before the system says so', () => {
    expect(html).not.toContain('nti-callout');
  });
});

describe('about page', () => {
  it('counts provinces with verified places from /api/provinces', () => {
    const data = { regions: [
      { region: 'เหนือ', provinces: [{ name: 'เชียงใหม่', verified_count: 24 }, { name: 'น่าน', verified_count: 0 }] },
      { region: 'ใต้', provinces: [{ name: 'ภูเก็ต', verified_count: 3 }] },
    ] };
    expect(coverageOf(data)).toEqual({ provinces: 3, withVerified: 2 });
    expect(coverageOf(null)).toEqual({ provinces: 0, withVerified: 0 });
  });
  it('shows licences for every outside data source', () => {
    const html = render(<About />);
    expect(html).toContain('© OpenStreetMap contributors');
    expect(html).toContain('CC BY-SA 4.0');
    expect(html).toContain('href="/privacy"');
  });
});

describe('provinces page', () => {
  const regions = [
    { region: 'เหนือ', provinces: [{ name: 'เชียงใหม่', verified_count: 24 }, { name: 'เชียงราย', verified_count: 11 }, { name: 'น่าน', verified_count: 6 }] },
    { region: 'ใต้', provinces: [{ name: 'ภูเก็ต', verified_count: 0 }] },
  ];
  it('filters by Thai or English name and drops empty regions', () => {
    expect(filterRegions(regions, 'เชียง').map((r) => r.provinces.length)).toEqual([2]);
    expect(filterRegions(regions, 'phuket')).toEqual([{ region: 'ใต้', provinces: [{ name: 'ภูเก็ต', verified_count: 0 }] }]);
    expect(filterRegions(regions, '')).toHaveLength(2);
    expect(filterRegions(regions, 'zzz')).toEqual([]);
  });
  it('renders a loading state before the list arrives', () => {
    expect(render(<Provinces />)).toContain('กำลังโหลด');
  });
});

describe('not found', () => {
  it('shows the missing path and ways out', () => {
    const html = render(<NotFound />, '/no-such-page');
    expect(html).toContain('/no-such-page');
    expect(html).toContain('href="/search"');
    expect(html).toContain('href="/provinces"');
  });
  it('is what the app shows for an unknown address, and every new page has a route', () => {
    // แอปทั้งตัวโหลด Leaflet ซึ่งต้องมี window จึงตรวจตารางเส้นทางจากซอร์สแทน
    expect(appSource).toContain('<Route path="*" element={<NotFound />} />');
    for (const r of ['/settings', '/provinces', '/about', '/privacy']) expect(appSource).toContain(`<Route path="${r}"`);
    for (const r of ['/about', '/provinces', '/privacy']) expect(appSource).toContain(`<Link to="${r}">`);
  });
});

describe('password form', () => {
  const ok = { current: 'old-password', next: 'new-password-1', confirm: 'new-password-1' };
  it('accepts a valid change', () => expect(passwordFormError(ok)).toBe(''));
  it.each([
    [{ ...ok, current: '' }, 'กรอกรหัสผ่านปัจจุบัน'],
    [{ ...ok, next: 'short', confirm: 'short' }, 'ต้องยาว'],
    [{ ...ok, next: 'x'.repeat(201), confirm: 'x'.repeat(201) }, 'ต้องยาว'],
    [{ ...ok, next: ok.current, confirm: ok.current }, 'ไม่ซ้ำ'],
    [{ ...ok, confirm: 'different-123' }, 'ไม่ตรงกัน'],
  ])('rejects %o', (form, msg) => expect(passwordFormError(form)).toContain(msg));
});
