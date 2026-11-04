import { describe, expect, it } from 'vitest';
import { CUES, HOP_MS, MIN_WALK, WEIGHTS, cueOf, pickAct, restAfter, roam, walkPlan, walkTarget } from './mascotMotion.js';
import { EXPRESSION_NAMES } from './mascot.js';

describe('ท่าทางเองของน้องทริป', () => {
  it('ระยะเดินคิดจากความกว้างเวทีลบตัวและขอบ เวทีแคบกว่าตัวได้ 0', () => {
    expect(roam(600, 250)).toBe(151);
    expect(roam(200, 250)).toBe(0);
  });

  it('สุ่มท่าตามน้ำหนัก ครอบคลุมทุกท่า และไม่กระโดดซ้ำติดกัน', () => {
    const seen = new Set();
    for (let i = 0; i < 100; i += 1) seen.add(pickAct(i / 100));
    expect([...seen].sort()).toEqual(Object.keys(WEIGHTS).sort());
    for (let i = 0; i < 100; i += 1) expect(pickAct(i / 100, 'hop')).not.toBe('hop');
    expect(pickAct(0)).toBe('walk');
    expect(pickAct(1)).toBe('rest');
  });

  it('จุดหมายเดินอยู่ในระยะและห่างจากที่เดิมพอ ไม่มีที่เดินคืน null', () => {
    for (let i = 0; i <= 20; i += 1) {
      for (const x of [-150, -40, 0, 60, 150]) {
        const to = walkTarget(i / 20, x, 150);
        expect(to).not.toBeNull();
        expect(Math.abs(to)).toBeLessThanOrEqual(150);
        expect(Math.abs(to - x)).toBeGreaterThanOrEqual(MIN_WALK);
      }
    }
    expect(walkTarget(0.5, 0, 10)).toBeNull();
  });

  it('เวลาเดินอยู่ในช่วงที่ดูเป็นธรรมชาติ และบอกทิศถูก', () => {
    expect(walkPlan(0, 10)).toMatchObject({ ms: 700, dir: 1 });
    expect(walkPlan(0, -1000)).toMatchObject({ ms: 3200, dir: -1 });
    expect(walkPlan(0, 120).steps).toBeGreaterThanOrEqual(2);
  });

  it('พักระหว่างท่านานพอไม่ให้วุ่นวาย', () => {
    expect(restAfter('peek', 0)).toBe(1600);
    expect(restAfter('walk', 1)).toBe(4400);
    expect(restAfter('hop', 0)).toBeGreaterThan(HOP_MS);
  });

  it('ทุกปฏิกิริยาต่อฟอร์มใช้สีหน้าที่มีภาพจริง', () => {
    for (const [name, cue] of Object.entries(CUES)) {
      expect(cueOf(name)).toBe(cue);
      if (cue.face) expect(EXPRESSION_NAMES).toContain(cue.face);
    }
    expect(cueOf('nope')).toBeNull();
  });
});
