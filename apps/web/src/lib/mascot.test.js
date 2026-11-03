import { describe, expect, it } from 'vitest';
import { BLINK_FRAMES, EXPRESSIONS, EXPRESSION_NAMES, expressionUrl, nextBlinkDelay, tapExpression } from './mascot.js';

describe('mascot expressions', () => {
  it('loads all 23 expressions plus the base', () => {
    expect(EXPRESSION_NAMES).toHaveLength(23);
    expect(EXPRESSIONS.front).toBeTruthy();
  });
  it('every blink frame exists', () => {
    for (const [name] of BLINK_FRAMES) expect(EXPRESSIONS[name]).toBeTruthy();
  });
  it('falls back to the base image for unknown names', () => {
    expect(expressionUrl('nope')).toBe(EXPRESSIONS.front);
  });
  it('escalates with repeated taps', () => {
    expect([1, 2, 3, 4, 5, 9].map(tapExpression)).toEqual(['grin', 'grin', 'ouch', 'ouch', 'angry', 'angry']);
  });
  it('blink delay stays within 3-6 seconds', () => {
    expect(nextBlinkDelay(0)).toBe(3000);
    expect(nextBlinkDelay(1)).toBe(6000);
  });
});
