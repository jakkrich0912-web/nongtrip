import { describe, expect, it } from 'vitest';
import {
  ACTS, GAZE_NAMES, HOVER_FACE, ROTATION, SPOT, TAP_FACE, allFaceNames, gazeFor, hasGaze, idleDue,
  isTap, nextIdleDelay, pressFace, releaseFace, resolveFace, shakeFace, takeAct, tapEscalation, zoneAt,
  FRONT_CANVAS,
} from './mascotPlay.js';
import { POSE_SETS } from './mascot.js';

const uv = (px, py) => [px / FRONT_CANVAS[0], py / FRONT_CANVAS[1]];

describe('zones on the front pose', () => {
  it('maps the parts of the cat the user can point at', () => {
    expect(zoneAt(...uv(230, 110))).toBe('hat');
    expect(zoneAt(...uv(308, 62))).toBe('pin');
    expect(zoneAt(...uv(158, 228))).toBe('eyeL');
    expect(zoneAt(...uv(300, 238))).toBe('eyeR');
    expect(zoneAt(...uv(232, 237))).toBe('nose');
    expect(zoneAt(...uv(228, 275))).toBe('mouth');
    expect(zoneAt(...uv(118, 264))).toBe('cheek');
    expect(zoneAt(...uv(332, 278))).toBe('cheek');
    expect(zoneAt(...uv(230, 200))).toBe('face');
    expect(zoneAt(...uv(220, 365))).toBe('camera');
    expect(zoneAt(...uv(230, 455))).toBe('belly');
    expect(zoneAt(...uv(230, 515))).toBe('feet');
  });
  it('hover only reacts on eyes, nose and mouth (forehead, cheeks and body stay calm)', () => {
    expect(Object.keys(HOVER_FACE).sort()).toEqual(['eyeL', 'eyeR', 'mouth', 'nose']);
    expect(HOVER_FACE.eyeL).toBe('wink-right');
    expect(HOVER_FACE.eyeR).toBe('wink-left');
  });
  it('every zone has a tap reaction', () => {
    for (const z of ['hat', 'pin', 'eyeL', 'eyeR', 'nose', 'mouth', 'cheek', 'face', 'camera', 'belly', 'feet']) {
      expect(TAP_FACE[z], z).toBeTruthy();
    }
    expect(TAP_FACE.nose).toBe('act:sneeze');
  });
});

describe('pull, release and shake', () => {
  it('pull distance moves her from calm to ouch to afraid', () => {
    expect(pressFace(0.01)).toBe(null);
    expect(pressFace(0.1)).toBe('ouch');
    expect(pressFace(0.3)).toBe('afraid');
  });
  it('after release she looks scrunched or dizzy; repeated pulls make her angry then cry', () => {
    expect(releaseFace(0.12, 1).face).toBe('squint');
    expect(releaseFace(0.3, 2).face).toBe('dizzy');
    expect(releaseFace(0.05, 1).face).toBe('blink-half');
    expect(releaseFace(0.3, 5).face).toBe('angry');
    expect(releaseFace(0.3, 8).face).toBe('crying');
  });
  it('a short press is a tap, a drag is not', () => {
    expect(isTap(0.01, 150)).toBe(true);
    expect(isTap(0.2, 150)).toBe(false);
    expect(isTap(0.01, 900)).toBe(false);
  });
  it('shaking the cursor scrunches her eyes and keeping it up makes her dizzy', () => {
    expect(shakeFace(0.2)).toBe(null);
    expect(shakeFace(0.7)).toBe('squint');
    expect(shakeFace(0.95)).toBe('dizzy');
  });
  it('tapping the same mascot fast five times makes her angry', () => {
    expect(tapEscalation(2, 'grin')).toBe('grin');
    expect(tapEscalation(5, 'grin')).toBe('angry');
  });
});

describe('idle acts', () => {
  it('start only after 30-45 seconds without input and never while pressed, acting or reduced motion', () => {
    expect(nextIdleDelay(0)).toBe(30000);
    expect(nextIdleDelay(1)).toBe(45000);
    const base = { now: 100000, lastInput: 50000, start: 0, nextIdle: 40000, reduced: false, pressed: false, acting: false };
    expect(idleDue(base)).toBe(true);
    expect(idleDue({ ...base, lastInput: 70000 })).toBe(false);
    expect(idleDue({ ...base, reduced: true })).toBe(false);
    expect(idleDue({ ...base, pressed: true })).toBe(false);
    expect(idleDue({ ...base, acting: true })).toBe(false);
    // ไม่เคยมีใครขยับเลย นับจากตอนเริ่ม
    expect(idleDue({ ...base, lastInput: -1e9, start: 80000 })).toBe(false);
  });
  it('rotates through every act before repeating', () => {
    const queue = [];
    const seen = [];
    for (let i = 0; i < ROTATION.length; i++) seen.push(takeAct(queue));
    expect(new Set(seen).size).toBe(ROTATION.length);
    expect(takeAct(queue)).toBe(ROTATION[0]);
  });
  it('every rotation entry is defined and every step is well formed', () => {
    for (const name of ROTATION) {
      const steps = ACTS[name];
      expect(Array.isArray(steps), name).toBe(true);
      for (const s of steps) {
        expect(typeof s.face).toBe('string');
        expect(s.hold).toBeGreaterThan(0);
        expect(s.fade).toBeGreaterThan(0);
      }
    }
    expect(SPOT.nose.length).toBe(2);
  });
});

describe('every face the logic can ask for exists in the front set', () => {
  it('has a picture for each name', () => {
    const missing = allFaceNames().filter((n) => !POSE_SETS.front.images[n]);
    expect(missing).toEqual([]);
  });
});

describe('other poses fall back to the pictures they have', () => {
  it('keeps negative faces on blink-half and positive ones on grin', () => {
    const wave = POSE_SETS.wave.images;
    expect(resolveFace(wave, 'angry')).toBe('blink-half');
    expect(resolveFace(wave, 'heart-eyes')).toBe('grin');
    expect(resolveFace(wave, 'grin')).toBe('grin');
    expect(resolveFace(wave, 'base')).toBe('base');
    const happy = POSE_SETS.happy.images;
    expect(resolveFace(happy, 'tongue')).toBe('base');
  });
});

describe('gaze (requires all 16 gaze pictures)', () => {
  it('picks one of sixteen directions and none near the centre', () => {
    expect(gazeFor(0.5, 0)).toBe('gaze-e');
    expect(gazeFor(-0.5, 0)).toBe('gaze-w');
    expect(gazeFor(0, -0.5)).toBe('gaze-n');
    expect(gazeFor(0, 0.5)).toBe('gaze-s');
    expect(gazeFor(0.4, -0.4)).toBe('gaze-ne');
    expect(gazeFor(0.01, 0.01)).toBe(null);
    expect(GAZE_NAMES).toHaveLength(16);
  });
  it('enables the complete front set and disables it if any direction is missing', () => {
    expect(hasGaze(POSE_SETS.front.images)).toBe(true);
    for (const missing of GAZE_NAMES) {
      const partial = { ...POSE_SETS.front.images };
      delete partial[missing];
      expect(hasGaze(partial), missing).toBe(false);
    }
  });
});
