/** Live stream source: Go2RTC (several transports) or processor detection MJPEG. */

export type LiveStreamKind =
  | 'go2rtc_auto'
  | 'go2rtc_webrtc'
  | 'go2rtc_mse'
  | 'go2rtc_mjpeg'
  | 'processor_detect';

export function resolveGo2rtcSrc(cam: {
  id: string;
  stream_url?: string;
  go2rtc_src?: string;
}): string {
  const explicit = (cam.go2rtc_src || '').trim();
  if (explicit) return explicit;
  const m = (cam.stream_url || '').match(/[?&]src=([^&]+)/);
  if (m?.[1]) {
    try {
      return decodeURIComponent(m[1]);
    } catch {
      return m[1];
    }
  }
  return cam.id;
}

export function go2rtcMjpegUrl(go2rtcSrc: string): string {
  return `/go2rtc/api/stream.mjpeg?src=${encodeURIComponent(go2rtcSrc)}`;
}

/** fMP4 / MSE (go2rtc). */
export function go2rtcMseUrl(go2rtcSrc: string): string {
  return `/go2rtc/api/stream.mp4?src=${encodeURIComponent(go2rtcSrc)}`;
}

export function go2rtcWebrtcPlayerUrl(go2rtcSrc: string): string {
  return `/go2rtc/stream.html?src=${encodeURIComponent(go2rtcSrc)}&mode=webrtc`;
}

export type LiveStreamRenderMode = 'img' | 'video' | 'iframe';

/** Фактический транспорт на кадре (для бейджа в UI). */
export type LiveStreamTransport =
  | 'processor_detect'
  | 'go2rtc_mse'
  | 'go2rtc_mjpeg'
  | 'go2rtc_mjpeg_fallback'
  | 'go2rtc_webrtc';

export type ResolvedLiveStream = {
  mode: LiveStreamRenderMode;
  src: string;
  /** When UI picked WebRTC iframe but editor needs aligned overlays — use MJPEG instead. */
  overlayAligned: boolean;
  transport: LiveStreamTransport;
};

export function resolveLiveStream({
  kind,
  go2rtcSrc,
  streamUrlMjpeg,
  preferOverlayAligned,
  mseFallback = false,
}: {
  kind: LiveStreamKind;
  go2rtcSrc: string;
  streamUrlMjpeg?: string;
  preferOverlayAligned?: boolean;
  /** MSE/video failed — auto and explicit MSE fall back to Go2RTC MJPEG. */
  mseFallback?: boolean;
}): ResolvedLiveStream | null {
  const processor = (streamUrlMjpeg || '').trim();
  const g2 = (go2rtcSrc || '').trim();

  if (kind === 'processor_detect') {
    if (!processor) return null;
    return {
      mode: 'img',
      src: processor,
      overlayAligned: true,
      transport: 'processor_detect',
    };
  }

  if (!g2) {
    if (processor) {
      return {
        mode: 'img',
        src: processor,
        overlayAligned: true,
        transport: 'processor_detect',
      };
    }
    return null;
  }

  if (kind === 'go2rtc_mjpeg' || (preferOverlayAligned && kind === 'go2rtc_webrtc')) {
    return {
      mode: 'img',
      src: go2rtcMjpegUrl(g2),
      overlayAligned: true,
      transport: 'go2rtc_mjpeg',
    };
  }

  if (kind === 'go2rtc_webrtc' && !preferOverlayAligned) {
    return {
      mode: 'iframe',
      src: go2rtcWebrtcPlayerUrl(g2),
      overlayAligned: false,
      transport: 'go2rtc_webrtc',
    };
  }

  if (!mseFallback && (kind === 'go2rtc_mse' || kind === 'go2rtc_auto')) {
    return {
      mode: 'video',
      src: go2rtcMseUrl(g2),
      overlayAligned: true,
      transport: 'go2rtc_mse',
    };
  }

  const fallback = mseFallback && (kind === 'go2rtc_auto' || kind === 'go2rtc_mse');
  return {
    mode: 'img',
    src: go2rtcMjpegUrl(g2),
    overlayAligned: true,
    transport: fallback ? 'go2rtc_mjpeg_fallback' : 'go2rtc_mjpeg',
  };
}

export function defaultLiveStreamKind(): LiveStreamKind {
  return 'go2rtc_auto';
}
