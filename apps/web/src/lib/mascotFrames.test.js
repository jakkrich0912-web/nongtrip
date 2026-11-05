import { describe, expect, it } from 'vitest';
import { MOTIONS, STILL, buildMotions, frameIndex, spriteBox, walkFps } from './mascotFrames.js';

describe('ภาพเคลื่อนไหวน้องทริป', () => {
  it('อ่านทั้ง 4 ชุดจาก manifest ครบทุกเฟรมตามจำนวนและ fps ที่กำหนด', () => {
    const want = { walk: [8, 10], hop: [6, 10], 'look-around': [6, 6], 'tail-wag': [4, 6] };
    for (const [name, [count, fps]] of Object.entries(want)) {
      expect(MOTIONS[name].frames).toHaveLength(count);
      expect(MOTIONS[name].fps).toBe(fps);
      expect(MOTIONS[name].canvas).toEqual([360, 480]);
      expect(MOTIONS[name].anchor).toEqual([180, 447]);
    }
    expect(MOTIONS.hop.lift).toEqual([0, 0, 26, 55, 0, 10]);   // เท้าลอยอยู่ในภาพแล้ว โค้ดไม่ชดเชย
  });

  it('ชุดที่เฟรมไม่ครบถูกข้ามทั้งชุด', () => {
    const manifests = { './x/manifest.json': { name: 'x', frame_count: 2, fps: 5, canvas_size: [1, 1], anchor: [0, 0], frames: [{ file: '00.webp' }, { file: '01.webp' }] } };
    expect(buildMotions(manifests, { './x/00.webp': 'a.webp' })).toEqual({});
    expect(Object.keys(buildMotions(manifests, { './x/00.webp': 'a', './x/01.webp': 'b' }))).toEqual(['x']);
  });

  it('จุดพื้นของภาพเคลื่อนไหวตรงกับปลายเท้าภาพนิ่ง และความสูงตัวเท่ากันทุกขนาด', () => {
    for (const size of [88, 250]) {
      const box = spriteBox(size, MOTIONS.walk);
      const s = size / STILL.source[0];
      expect(box.left + box.originX).toBeCloseTo(STILL.cx * s, 1);
      expect(box.top + box.originY).toBeCloseTo(STILL.bottom * s, 1);
      expect(389 * box.scale).toBeCloseTo(STILL.height * s, 1);
      expect(box.width / box.height).toBeCloseTo(360 / 480, 2);   // สัดส่วนผืน 3:4 คงที่
    }
  });

  it('frameIndex วนตาม fps เล่นครบจำนวนรอบแล้วคืน -1', () => {
    expect(frameIndex(0, 10, 6, 1)).toBe(0);
    expect(frameIndex(250, 10, 6, 1)).toBe(2);
    expect(frameIndex(599, 10, 6, 1)).toBe(5);
    expect(frameIndex(600, 10, 6, 1)).toBe(-1);
    expect(frameIndex(1000, 6, 4, 2)).toBe(2);
    expect(frameIndex(1334, 6, 4, 2)).toBe(-1);
    expect(frameIndex(10_000, 10, 8)).toBe(4);                   // วนไม่จบ
    expect(frameIndex(100, 0, 8)).toBe(-1);
  });

  it('fps ของท่าเดินเพิ่มตามความเร็ว และอยู่ในช่วง 5-14', () => {
    const slow = walkFps(40, 250);
    const fast = walkFps(200, 250);
    expect(fast).toBeGreaterThan(slow);
    expect(walkFps(1, 250)).toBe(5);
    expect(walkFps(10_000, 250)).toBe(14);
  });
});
