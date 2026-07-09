import { describe, expect, it } from 'vitest';
import { resolveFrameAtTime, type AnnotationFrame } from './AnnotationViewer';

const frames: AnnotationFrame[] = [
  { t: 0, bbox: [0.1, 0.1, 0.1, 0.1] },
  { t: 2, bbox: [0.3, 0.1, 0.1, 0.1] },
];

describe('resolveFrameAtTime', () => {
  it('returns null outside keyframe span', () => {
    expect(resolveFrameAtTime(frames, -0.1)).toBeNull();
    expect(resolveFrameAtTime(frames, 2.5)).toBeNull();
  });

  it('interpolates bbox between keyframes', () => {
    const mid = resolveFrameAtTime(frames, 1);
    expect(mid).not.toBeNull();
    expect(mid!.bbox[0]).toBeCloseTo(0.2, 5);
  });

  it('returns null for empty frames', () => {
    expect(resolveFrameAtTime([], 1)).toBeNull();
  });
});
