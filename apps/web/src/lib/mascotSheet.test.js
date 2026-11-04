import { describe, expect, it } from 'vitest';
import { createSheet, OVER, STEP } from './mascotSheet.js';

// สุ่มแบบซ้ำได้ เทสต์จะได้ไม่ผันผวน
const rng = (seed) => () => { seed = (seed * 1664525 + 1013904223) >>> 0; return seed / 2 ** 32; };

function frames(sheet, seconds, dt = 1 / 60) {
  for (let t = 0; t < seconds; t += dt) sheet.advance(dt);
}

describe('mascot sheet physics', () => {
  it('starts flat and covers OVER times the picture', () => {
    const sheet = createSheet({ n: 24 });
    sheet.advance(1 / 60);
    expect(sheet.energy()).toBe(0);
    expect(sheet.rest[0]).toBeCloseTo(0.5 - OVER / 2, 6);
    expect(sheet.rest[(sheet.count - 1) * 2]).toBeCloseTo(0.5 + OVER / 2, 6);
    expect(sheet.index.length).toBe(24 * 24 * 6);
  });

  it('stretches under a hold and rings back to rest after release', () => {
    const sheet = createSheet({ n: 40 });
    sheet.takeHold(0.5, 0.45);
    sheet.dragTo(0.5, 0.75);
    frames(sheet, 0.4);
    const stretched = sheet.energy();
    expect(stretched).toBeGreaterThan(1);
    sheet.releaseHold();
    frames(sheet, 4);
    expect(sheet.energy()).toBeLessThan(stretched * 0.02);
  });

  it('caps the pull distance so the slope cannot fold', () => {
    const sheet = createSheet({ n: 32 });
    sheet.takeHold(0.5, 0.5);
    const d = sheet.dragTo(5, 5);
    expect(d).toBeLessThanOrEqual(0.24 + 1e-6);
    expect(sheet.pull()).toBeLessThanOrEqual(0.24 + 1e-6);
  });

  it('never folds: rows and columns stay in order under violent pulls and pokes', () => {
    const sheet = createSheet({ n: 40 });
    const rand = rng(7);
    let worst = Infinity;
    for (let round = 0; round < 40; round++) {
      sheet.takeHold(rand(), rand(), 0.1 + rand() * 0.2);
      sheet.dragTo(rand() * 2 - 0.5, rand() * 2 - 0.5);
      sheet.poke(rand(), rand(), (rand() - 0.5) * 6, (rand() - 0.5) * 6);
      for (let i = 0; i < 30; i++) {
        sheet.advance(1 / 60);
        const g = sheet.minGaps();
        worst = Math.min(worst, g.x, g.y);
      }
      if (round % 3 === 0) sheet.releaseHold();
    }
    expect(worst).toBeGreaterThan(0);
    expect(worst).toBeGreaterThanOrEqual(sheet.gap * 0.3);
  });

  it('does not blow up: displacements stay bounded and finite', () => {
    const sheet = createSheet({ n: 40 });
    sheet.poke(0.5, 0.5, 40, -40, 0.2);
    sheet.takeHold(0.3, 0.3);
    sheet.dragTo(0.9, 0.9);
    frames(sheet, 3);
    for (let i = 0; i < sheet.dyn.length; i++) {
      expect(Number.isFinite(sheet.dyn[i])).toBe(true);
    }
    // ทุกปมยังอยู่ในระยะสมเหตุสมผลของภาพ (ไม่กระเด็นไปไกล)
    for (let k = 0; k < sheet.count; k++) {
      expect(Math.abs(sheet.dyn[k * 3])).toBeLessThan(1.2);
      expect(Math.abs(sheet.dyn[k * 3 + 1])).toBeLessThan(1.2);
    }
  });

  it('runs physics at a fixed step whatever the frame rate', () => {
    const slow = createSheet({ n: 24 });
    const fast = createSheet({ n: 24 });
    for (const s of [slow, fast]) s.poke(0.5, 0.5, 3, 2, 0.15);
    // เวลารวมเท่ากัน 1 วินาที: 30 เฟรม (8 ก้าวต่อเฟรม ไม่ถึงเพดาน 9) เทียบกับ 120 เฟรม
    for (let i = 0; i < 30; i++) slow.advance(1 / 30 - 1e-9);
    for (let i = 0; i < 120; i++) fast.advance(1 / 120 - 1e-9);
    let diff = 0; let total = 0;
    for (let k = 0; k < slow.count; k++) { diff += Math.abs(slow.ux[k] - fast.ux[k]); total += Math.abs(fast.ux[k]); }
    expect(diff / (total + 1e-9)).toBeLessThan(0.06);
    expect(STEP).toBeCloseTo(1 / 240, 8);
  });

  it('a hand placed directly still cannot fold the sheet', () => {
    const sheet = createSheet({ n: 40 });
    sheet.takeHold(0.8, 0.5);
    sheet.setHand(0.6, -0.1);
    let worst = Infinity;
    for (let i = 0; i < 90; i++) { sheet.advance(1 / 60); const g = sheet.minGaps(); worst = Math.min(worst, g.x, g.y); }
    expect(worst).toBeGreaterThan(0);
  });

  it('settle() clears all motion', () => {
    const sheet = createSheet({ n: 24 });
    sheet.poke(0.5, 0.5, 5, 5);
    frames(sheet, 0.1);
    expect(sheet.energy()).toBeGreaterThan(0);
    sheet.settle();
    expect(sheet.energy()).toBe(0);
  });
});
