import { describe, expect, it } from 'vitest';
import { initialOf } from './AccountMenu.jsx';
import headerSource from './SiteHeader.jsx?raw';

describe('account menu', () => {
  it('uses the first letter of the email, upper-cased', () => {
    expect(initialOf('jakkrich0912@gmail.com')).toBe('J');
    expect(initialOf('  ana@example.com')).toBe('A');
    expect(initialOf('สมชาย@example.com')).toBe('ส');
    expect(initialOf('')).toBe('?');
    expect(initialOf(undefined)).toBe('?');
  });
  it('replaces the "My trips" text link with the menu once signed in', () => {
    expect(headerSource).toContain('{user ? <AccountMenu /> :');
    expect(headerSource).not.toContain("user ? t('ทริปของฉัน'");
  });
});
