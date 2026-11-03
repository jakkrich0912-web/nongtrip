import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { BLINK_FRAMES, EXPRESSIONS, EXPRESSION_NAMES, POSE_SETS, expressionUrl, nextBlinkDelay, poseFrame, poseUrl, tapExpression } from './mascot.js';

const manifest = (pose) => JSON.parse(readFileSync(new URL(`../assets/mascot/expressions-v2/${pose === 'front' ? '' : `${pose}/`}manifest.json`, import.meta.url), 'utf8'));

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

describe('mascot poses', () => {
  it('geometry matches each manifest (canvas, source size, offset)', () => {
    for (const pose of ['front', 'wave', 'think', 'happy']) {
      const m = manifest(pose);
      expect(POSE_SETS[pose].canvas, pose).toEqual(m.canvas_size);
      expect(POSE_SETS[pose].source, pose).toEqual(m.source_size);
      expect(POSE_SETS[pose].offset, pose).toEqual(m.source_offset);
    }
  });
  it('every pose has a base image and every expression its manifest promises', () => {
    for (const pose of ['wave', 'think', 'happy']) {
      const m = manifest(pose);
      expect(poseUrl(pose, 'base'), pose).toBeTruthy();
      for (const name of m.expected_expressions) expect(POSE_SETS[pose].images[name], `${pose}/${name}`).toBeTruthy();
    }
  });
  it('wave and think blink and grin, happy does not blink on its own', () => {
    for (const pose of ['wave', 'think']) {
      expect(POSE_SETS[pose].blink).toBe(true);
      for (const [name] of BLINK_FRAMES) expect(POSE_SETS[pose].images[name]).toBeTruthy();
      expect(POSE_SETS[pose].images[POSE_SETS[pose].tap(1)]).toBeTruthy();
    }
    expect(POSE_SETS.happy.blink).toBe(false);
    expect(POSE_SETS.happy.images[POSE_SETS.happy.tap(1)]).toBeTruthy();
  });
  it('unknown names fall back to the pose base, never to another pose', () => {
    expect(poseUrl('wave', 'nope')).toBe(POSE_SETS.wave.images.base);
    expect(poseUrl('happy', 'grin')).toBe(POSE_SETS.happy.images.base);
    expect(poseUrl('front', 'nope')).toBe(EXPRESSIONS.front);
  });
  it('front keeps exactly the frame it had before', () => {
    expect(poseFrame('front')).toEqual({
      frame: { aspectRatio: '373 / 520' },
      image: { left: '-6.1662%', top: '-3.8462%', width: '112.6005%' },
    });
  });
  it('the frame keeps the original aspect ratio so page layout does not move', () => {
    expect(poseFrame('wave').frame.aspectRatio).toBe('400 / 517');
    expect(poseFrame('think').frame.aspectRatio).toBe('400 / 499');
    expect(poseFrame('happy').frame.aspectRatio).toBe('397 / 517');
  });
});

