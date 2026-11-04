import { describe, expect, it } from 'vitest';
import { applyTheme, readTheme } from './theme.js';

const store = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) };
};

describe('theme', () => {
  it('defaults to light and ignores junk', () => {
    expect(readTheme(store())).toBe('light');
    expect(readTheme(store({ 'nongtrip-theme': 'purple' }))).toBe('light');
    expect(readTheme({ getItem: () => { throw new Error('blocked'); } })).toBe('light');
  });
  it('remembers and applies the choice', () => {
    const s = store();
    const doc = { documentElement: { dataset: {} } };
    expect(applyTheme('dark', doc, s)).toBe('dark');
    expect(doc.documentElement.dataset.theme).toBe('dark');
    expect(readTheme(s)).toBe('dark');
    expect(applyTheme('nonsense', doc, s)).toBe('light');
  });
});
