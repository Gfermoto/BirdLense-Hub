import { describe, expect, it } from 'vitest';
import { go2rtcFrameJpegUrl, resolveLiveStream } from './liveStream';

describe('resolveLiveStream', () => {
  it('uses frame.jpeg polling for go2rtc_mjpeg (H264 RTSP has no native mjpeg)', () => {
    const r = resolveLiveStream({
      kind: 'go2rtc_mjpeg',
      go2rtcSrc: 'BirdBox',
    });
    expect(r?.mode).toBe('img');
    expect(r?.src).toBe(go2rtcFrameJpegUrl('BirdBox'));
    expect(r?.framePollMs).toBeGreaterThan(0);
    expect(r?.transport).toBe('go2rtc_mjpeg');
  });

  it('webrtc iframe uses webrtc-only mode (no silent MSE fallback)', () => {
    const r = resolveLiveStream({
      kind: 'go2rtc_webrtc',
      go2rtcSrc: 'Forest',
      preferOverlayAligned: false,
    });
    expect(r?.mode).toBe('iframe');
    expect(r?.src).toContain('mode=webrtc');
    expect(r?.src).not.toContain('mse');
  });
});
