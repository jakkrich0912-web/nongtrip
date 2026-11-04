import { describe, expect, it } from 'vitest';
import { graphemeEnds, stepFor } from './typewriter.js';

describe('typewriter', () => {
  it('never cuts Thai vowels or tone marks off their consonant', () => {
    const text = 'น้ำตก';
    const cuts = graphemeEnds(text).map((end) => text.slice(0, end));
    expect(cuts).toEqual(['น้ำ', 'น้ำต', 'น้ำตก']);
  });
  it('handles empty text', () => {
    expect(graphemeEnds('')).toEqual([]);
  });
  it('speeds up when far behind but always moves', () => {
    expect(stepFor(1)).toBe(1);
    expect(stepFor(24)).toBe(2);
    expect(stepFor(600)).toBe(50);
  });
});
