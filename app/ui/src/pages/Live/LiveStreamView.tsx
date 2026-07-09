import { useEffect, useMemo, useState, type ReactNode } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { LiveMediaStage } from './LiveMediaStage';
import {
  resolveLiveStream,
  type LiveStreamKind,
  type LiveStreamTransport,
} from './liveStream';

function streamTransportLabel(
  transport: LiveStreamTransport,
  t: (key: string) => string,
): string {
  const key = `live.streamTransport.${transport}` as const;
  const label = t(key);
  return label === key ? transport : label;
}

export function LiveStreamView({
  name,
  streamKind,
  go2rtcSrc,
  streamUrlMjpeg,
  preferOverlayAligned = false,
  overlay,
  onOverlayClick,
  overlayPointerEvents = 'none',
  sx,
}: {
  name: string;
  streamKind: LiveStreamKind;
  go2rtcSrc: string;
  streamUrlMjpeg?: string;
  preferOverlayAligned?: boolean;
  overlay?: ReactNode;
  onOverlayClick?: (e: React.MouseEvent<SVGSVGElement>) => void;
  overlayPointerEvents?: 'auto' | 'none';
  sx?: Record<string, unknown>;
}) {
  const { t } = useTranslation();
  const [mseFailed, setMseFailed] = useState(false);

  useEffect(() => {
    setMseFailed(false);
  }, [streamKind, go2rtcSrc]);

  const resolved = useMemo(() => {
    let kind = streamKind;
    if (mseFailed && (kind === 'go2rtc_auto' || kind === 'go2rtc_mse')) {
      kind = 'go2rtc_mjpeg';
    }
    return resolveLiveStream({
      kind,
      go2rtcSrc,
      streamUrlMjpeg,
      preferOverlayAligned,
      mseFallback: mseFailed,
    });
  }, [streamKind, go2rtcSrc, streamUrlMjpeg, preferOverlayAligned, mseFailed]);

  const frameLabel = resolved
    ? streamTransportLabel(resolved.transport, t)
    : undefined;

  if (!resolved?.src) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          bgcolor: 'black',
          ...sx,
        }}
      >
        <Typography color="text.secondary">{t('live.streamUnavailable')}</Typography>
      </Box>
    );
  }

  if (resolved.mode === 'iframe') {
    return (
      <Box sx={{ position: 'relative', width: '100%', height: '100%', ...sx }}>
        <Box
          component="iframe"
          title={name}
          src={resolved.src}
          sx={{
            width: '100%',
            height: '100%',
            border: 0,
            bgcolor: 'black',
          }}
        />
        {frameLabel ? (
          <Box
            sx={{
              position: 'absolute',
              left: 8,
              top: 8,
              zIndex: 3,
              px: 1,
              py: 0.35,
              borderRadius: 0.75,
              bgcolor: 'rgba(0, 0, 0, 0.72)',
              color: 'common.white',
              typography: 'caption',
              fontWeight: 700,
              pointerEvents: 'none',
            }}
          >
            {frameLabel}
          </Box>
        ) : null}
      </Box>
    );
  }

  return (
    <LiveMediaStage
      kind={resolved.mode === 'video' ? 'video' : 'img'}
      src={resolved.src}
      framePollMs={resolved.framePollMs}
      alt={name}
      frameLabel={frameLabel}
      onMediaError={() => {
        if (
          !mseFailed &&
          go2rtcSrc &&
          (streamKind === 'go2rtc_auto' || streamKind === 'go2rtc_mse')
        ) {
          setMseFailed(true);
        }
      }}
      overlay={overlay}
      onOverlayClick={onOverlayClick}
      overlayPointerEvents={overlayPointerEvents}
      sx={sx}
    />
  );
}

/** Grid tile: img with go2rtc MJPEG fallback when MSE/video fails. */
export function LiveStreamTile({
  name,
  streamKind,
  go2rtcSrc,
  streamUrlMjpeg,
  sx,
}: {
  name: string;
  streamKind: LiveStreamKind;
  go2rtcSrc: string;
  streamUrlMjpeg?: string;
  sx?: Record<string, unknown>;
}) {
  return (
    <LiveStreamView
      name={name}
      streamKind={streamKind}
      go2rtcSrc={go2rtcSrc}
      streamUrlMjpeg={streamUrlMjpeg}
      preferOverlayAligned={false}
      sx={sx}
    />
  );
}

export function liveStreamKindHasGo2rtc(kind: LiveStreamKind): boolean {
  return kind !== 'processor_detect';
}
