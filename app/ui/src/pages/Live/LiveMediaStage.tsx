import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from 'react';
import Box from '@mui/material/Box';
import type { SxProps, Theme } from '@mui/material/styles';

export type MediaLayoutRect = {
  left: number;
  top: number;
  width: number;
  height: number;
};

type MediaKind = 'img' | 'video';

function readMediaDimensions(el: HTMLImageElement | HTMLVideoElement): { w: number; h: number } {
  if (el instanceof HTMLVideoElement) {
    return { w: el.videoWidth, h: el.videoHeight };
  }
  return { w: el.naturalWidth, h: el.naturalHeight };
}

function computeContainRect(
  containerW: number,
  containerH: number,
  mediaW: number,
  mediaH: number,
): MediaLayoutRect | null {
  if (containerW <= 0 || containerH <= 0 || mediaW <= 0 || mediaH <= 0) {
    return null;
  }
  const scale = Math.min(containerW / mediaW, containerH / mediaH);
  const width = mediaW * scale;
  const height = mediaH * scale;
  return {
    left: (containerW - width) / 2,
    top: (containerH - height) / 2,
    width,
    height,
  };
}

export function LiveMediaStage({
  kind,
  src,
  alt,
  onMediaError,
  overlay,
  onOverlayClick,
  overlayPointerEvents = 'none',
  frameLabel,
  framePollMs,
  sx,
}: {
  kind: MediaKind;
  src: string;
  alt: string;
  onMediaError?: () => void;
  overlay?: ReactNode;
  onOverlayClick?: (e: React.MouseEvent<SVGSVGElement>) => void;
  overlayPointerEvents?: 'auto' | 'none';
  /** Транспорт потока (MSE, MJPEG, …) — в углу кадра. */
  frameLabel?: string;
  /** Poll go2rtc frame.jpeg (H264 RTSP has no native /api/stream.mjpeg). */
  framePollMs?: number;
  sx?: SxProps<Theme>;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mediaRef = useRef<HTMLImageElement | HTMLVideoElement>(null);
  const [layout, setLayout] = useState<MediaLayoutRect | null>(null);
  const [pollTick, setPollTick] = useState(0);

  const updateLayout = useCallback(() => {
    const container = containerRef.current;
    const media = mediaRef.current;
    if (!container || !media) return;
    const { w, h } = readMediaDimensions(media);
    const next = computeContainRect(container.clientWidth, container.clientHeight, w, h);
    setLayout(next);
  }, []);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const ro = new ResizeObserver(() => updateLayout());
    ro.observe(container);
    return () => ro.disconnect();
  }, [updateLayout, src, kind]);

  useEffect(() => {
    if (!framePollMs || framePollMs <= 0 || kind !== 'img') return;
    const id = window.setInterval(() => setPollTick((t) => t + 1), framePollMs);
    return () => window.clearInterval(id);
  }, [framePollMs, kind, src]);

  const mediaSrc =
    framePollMs && framePollMs > 0 && kind === 'img'
      ? `${src}${src.includes('?') ? '&' : '?'}_t=${pollTick}`
      : src;

  const mediaSx = {
    position: 'absolute',
    inset: 0,
    width: '100%',
    height: '100%',
    objectFit: 'contain',
  } as const;

  return (
    <Box
      ref={containerRef}
      sx={{
        position: 'relative',
        width: '100%',
        height: '100%',
        overflow: 'hidden',
        bgcolor: 'black',
        ...sx,
      }}
    >
      {kind === 'video' ? (
        <Box
          component="video"
          ref={mediaRef as RefObject<HTMLVideoElement>}
          src={src}
          autoPlay
          muted
          playsInline
          onLoadedMetadata={updateLayout}
          onResize={updateLayout}
          onError={onMediaError}
          sx={mediaSx}
        />
      ) : (
        <Box
          component="img"
          ref={mediaRef as RefObject<HTMLImageElement>}
          src={mediaSrc}
          alt={alt}
          onLoad={updateLayout}
          onError={onMediaError}
          sx={mediaSx}
        />
      )}
      {frameLabel ? (
        <Box
          sx={{
            position: 'absolute',
            left: layout ? layout.left + 8 : 8,
            top: layout ? layout.top + 8 : 8,
            zIndex: 3,
            px: 1,
            py: 0.35,
            borderRadius: 0.75,
            bgcolor: 'rgba(0, 0, 0, 0.72)',
            color: 'common.white',
            typography: 'caption',
            fontWeight: 700,
            letterSpacing: 0.02,
            lineHeight: 1.2,
            minHeight: '1.5em',
            minWidth: '3.5em',
            pointerEvents: 'none',
            userSelect: 'none',
            opacity: layout ? 1 : 0.55,
          }}
        >
          {frameLabel}
        </Box>
      ) : null}
      {layout && overlay ? (
        <Box
          component="svg"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          onClick={onOverlayClick}
          sx={{
            position: 'absolute',
            left: layout.left,
            top: layout.top,
            width: layout.width,
            height: layout.height,
            pointerEvents: overlayPointerEvents,
            zIndex: 2,
          }}
        >
          {overlay}
        </Box>
      ) : null}
    </Box>
  );
}
