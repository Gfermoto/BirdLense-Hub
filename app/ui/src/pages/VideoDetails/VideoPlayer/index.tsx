import React, {
  useRef,
  useState,
  useMemo,
  useCallback,
  useEffect,
} from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
import Tab from '@mui/material/Tab';
import Tabs from '@mui/material/Tabs';
import Chip from '@mui/material/Chip';
import Fade from '@mui/material/Fade';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import { Video, VideoSpecies } from '../../../types';
import { resolveImageUrl } from '../../../api/api';
import { BASE_API_URL, BASE_URL } from '../../../api/client';
import { ProgressBar } from './ProgressBar';
import { SpectrogramPlayer } from './SpectrogramPlayer';
import { useTranslation } from 'react-i18next';
import { useVideoControl } from './useVideoControl';
import { AnnotationViewer } from '../../../components/AnnotationViewer';
import { SpeciesIcon } from '../../../components/SpeciesIcon';
import { useProtectedArea } from '../../../contexts/ProtectedAreaContext';

interface ViewToggleProps {
  view: 'video' | 'audio';
  onChange: (view: 'video' | 'audio') => void;
}

interface VideoPlayerProps {
  video: Video;
  /** After detection-frames load: video has YOLO rows but no bbox frames in DB */
  showTracksRegenHint?: boolean;
}

const ViewToggle: React.FC<ViewToggleProps> = ({ view, onChange }) => {
  const { t } = useTranslation();
  return (
    <Box
      sx={{
        position: 'absolute',
        top: 16,
        left: 16,
        zIndex: 10,
        bgcolor: 'rgba(0, 0, 0, 0.6)',
        borderRadius: 1,
        backdropFilter: 'blur(4px)',
      }}
    >
      <Tabs
        value={view}
        onChange={(_, newView) => onChange(newView)}
        aria-label={t('video.mediaViewTabs')}
        sx={{
          minHeight: 'auto',
          '& .MuiTab-root': {
            minHeight: 32,
            color: 'rgba(255, 255, 255, 0.7)',
            '&.Mui-selected': {
              color: 'white',
            },
          },
          '& .MuiTabs-indicator': {
            backgroundColor: 'primary.main',
          },
        }}
      >
        <Tab label={t('video.video')} value="video" sx={{ py: 0.5, px: 2 }} />
        <Tab
          label={t('video.spectrogram')}
          value="audio"
          sx={{ py: 0.5, px: 2 }}
        />
      </Tabs>
    </Box>
  );
};

// Compact overlay for active species detection
interface CompactDetectionOverlayProps {
  species: VideoSpecies[];
}

const CompactDetectionOverlay: React.FC<CompactDetectionOverlayProps> = ({
  species,
}) => {
  const { t } = useTranslation();
  if (species.length === 0) {
    return null;
  }

  return (
    <Fade in timeout={300}>
      <Box
        sx={{
          position: 'absolute',
          bottom: 8,
          left: 8,
          zIndex: 10,
          display: 'flex',
          flexDirection: 'column',
          gap: 0.5,
          maxWidth: { xs: '50%' },
        }}
      >
        {species.map((s, index) => (
          <Box
            key={`${s.species_id}-${s.start_time}-${index}`}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              bgcolor: 'rgba(0, 0, 0, 0.7)',
              backdropFilter: 'blur(4px)',
              borderRadius: 1,
              px: 1.5,
              py: 0.75,
            }}
          >
            <SpeciesIcon
              speciesName={s.species_name}
              imageUrl={s.image_url}
              size={24}
            />
            <Typography
              variant="body2"
              noWrap
              sx={{
                color: 'white',
                fontWeight: 500,
                fontSize: { xs: '0.75rem', sm: '0.875rem' },
                maxWidth: { xs: 120, sm: 200 },
              }}
            >
              {s.species_name}
            </Typography>
            <Chip
              label={`${Math.round(s.confidence * 100)}%`}
              title={`${t('video.confidence')}: ${Math.round(s.confidence * 100)}%`}
              size="small"
              color="primary"
              sx={{
                height: { xs: 18, sm: 20 },
                fontSize: { xs: '0.65rem', sm: '0.7rem' },
                flexShrink: 0,
              }}
            />
          </Box>
        ))}
      </Box>
    </Fade>
  );
};

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  video,
  showTracksRegenHint = false,
}) => {
  const { t } = useTranslation();
  const { isAdmin } = useProtectedArea();
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const timeoutRef = useRef<number | undefined>(undefined);
  const [view, setView] = useState<'video' | 'audio'>('video');
  const [error, setError] = useState<string | null>(null);

  // Reset error when video changes to avoid showing a stale error for a new video
  useEffect(() => {
    setError(null);
  }, [video.id]);
  const [showControls, setShowControls] = useState(true);
  const [showTracks, setShowTracks] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1);

  const SPEED_OPTIONS = [0.5, 1, 2] as const;

  const { playing, progress, handleProgress, handleSeek, togglePlayPause } =
    useVideoControl(videoRef);

  const duration = useMemo(
    () =>
      Math.max(
        0,
        (new Date(video.end_time).getTime() -
          new Date(video.start_time).getTime()) /
          1000,
      ),
    [video.end_time, video.start_time],
  );

  const filteredDetections = useMemo(
    () =>
      video.species
        .filter((s) => s.source === view)
        .sort((a, b) => a.start_time - b.start_time),
    [video.species, view],
  );

  const spectrogramDetections = useMemo(
    () => [...video.species].sort((a, b) => a.start_time - b.start_time),
    [video.species],
  );

  // Get video detections that have track frames data
  const trackDetections = useMemo(
    () =>
      video.species.filter(
        (s) => s.source === 'video' && s.frames && s.frames.length > 0,
      ),
    [video.species],
  );
  const trackAnnotations = useMemo(
    () =>
      trackDetections
        .map((s, idx) => {
          const frames =
            s.frames?.map((f) => {
              const [x1, y1, x2, y2] = f.bbox;
              return {
                t: f.t,
                bbox: [x1, y1, Math.max(0, x2 - x1), Math.max(0, y2 - y1)] as [number, number, number, number],
              };
            }) || [];
          if (!frames.length) return null;
          return {
            id: `video-track-${s.species_id}-${s.track_id ?? idx}`,
            label: `${s.species_name} (${Math.round((s.confidence || 0) * 100)}%)`,
            color: '#22c55e',
            frames,
          };
        })
        .filter(Boolean) as Array<{
        id: string;
        label: string;
        color: string;
        frames: Array<{ t: number | null; bbox: [number, number, number, number] }>;
      }>,
    [trackDetections],
  );

  useEffect(() => {
    if (trackDetections.length > 0) {
      setShowTracks(true);
    }
  }, [trackDetections.length]);

  const activeDetections = useMemo(
    () =>
      filteredDetections.filter(
        (species) =>
          progress >= species.start_time && progress <= species.end_time,
      ),
    [progress, filteredDetections],
  );

  // При смене видео без спектрограммы — сброс на video, иначе SpectrogramPlayer получит неверный URL
  useEffect(() => {
    if (!video.spectrogram_path && view === 'audio') {
      setView('video');
    }
  }, [video?.id, video?.spectrogram_path, view]);

  // Reset speed when switching video
  useEffect(() => {
    setPlaybackRate(1);
  }, [video?.id]);

  // Apply playback rate to video element
  useEffect(() => {
    const el = videoRef.current;
    if (el) el.playbackRate = playbackRate;
  }, [playbackRate]);

  const startHideTimer = useCallback(() => {
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
    }
    if (playing) {
      timeoutRef.current = window.setTimeout(() => {
        setShowControls(false);
      }, 1000);
    }
  }, [playing]);

  const handleMouseMove = useCallback(() => {
    setShowControls(true);
    startHideTimer();
  }, [startHideTimer]);

  const handleTouch = useCallback(() => {
    setShowControls(true);
    startHideTimer();
  }, [startHideTimer]);

  const handleFullscreen = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;

    const v = video as HTMLVideoElement & {
      webkitEnterFullscreen?: () => void;
      webkitSupportsFullscreen?: boolean;
    };

    // iOS Safari: webkitEnterFullscreen on <video> (iPad works; iPhone may fallback to native)
    if (typeof v.webkitEnterFullscreen === 'function') {
      try {
        v.webkitEnterFullscreen();
      } catch (err) {
        console.warn(
          'webkitEnterFullscreen failed, trying native controls:',
          err,
        );
        video.controls = true;
      }
      return;
    }

    // Standard Fullscreen API (desktop, Android)
    if (typeof video.requestFullscreen === 'function') {
      video
        .requestFullscreen()
        .then(() => {
          if (videoRef.current) videoRef.current.controls = true;
        })
        .catch((err) => {
          console.warn('requestFullscreen failed:', err);
          video.controls = true;
        });
    } else {
      video.controls = true;
    }
  }, []);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const hideControls = () => {
      if (videoRef.current) videoRef.current.controls = false;
    };

    const handleFullscreenChange = () => {
      if (!document.fullscreenElement) hideControls();
    };

    const handleWebkitEndFullscreen = () => hideControls();

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    video.addEventListener('webkitendfullscreen', handleWebkitEndFullscreen);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
      video.removeEventListener(
        'webkitendfullscreen',
        handleWebkitEndFullscreen,
      );
    };
  }, []);

  // Show controls when video is paused
  useEffect(() => {
    if (!playing) {
      setShowControls(true);
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
    } else {
      startHideTimer();
    }
    // Clean up timeout on unmount
    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
      }
    };
  }, [playing, startHideTimer]);

  if (error) {
    return (
      <Box sx={{ px: 2, py: 2 }}>
        <Typography color="error" align="center" sx={{ mb: 1 }}>
          {error}
        </Typography>
        <Typography variant="body2" color="text.secondary" align="center">
          {t('errors.loadVideoHint')}
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      <Box
        sx={{
          width: '100%',
          aspectRatio: '16 / 9', // Enforce 16:9 aspect ratio
          position: 'relative',
          mt: 0, // Removed top margin for cleaner alignment
        }}
        onMouseMove={handleMouseMove}
        onTouchStart={handleTouch}
      >
        {/* Overlay Tabs — только если есть спектрограмма (BirdNET при записи) */}
        {showControls && video.spectrogram_path && (
          <ViewToggle view={view} onChange={setView} />
        )}

        {/* Tracks toggle: не привязываем к showControls — иначе при воспроизведении
            переключатель исчезает вместе с остальными контролами */}
        {view === 'video' && trackDetections.length > 0 && (
          <Box
            sx={{
              position: 'absolute',
              top: 16,
              right: 16,
              zIndex: 11,
              bgcolor: 'rgba(0, 0, 0, 0.6)',
              borderRadius: 1,
              backdropFilter: 'blur(4px)',
              px: 1.5,
              py: 0.5,
            }}
          >
            <FormControlLabel
              control={
                <Switch
                  size="small"
                  checked={showTracks}
                  onChange={(e) => setShowTracks(e.target.checked)}
                  sx={{
                    '& .MuiSwitch-thumb': { width: 14, height: 14 },
                    '& .MuiSwitch-switchBase': { padding: '6px' },
                  }}
                />
              }
              label={t('commonLabels.tracks')}
              sx={{
                margin: 0,
                '& .MuiFormControlLabel-label': {
                  color: 'rgba(255, 255, 255, 0.9)',
                  fontSize: '0.75rem',
                  ml: 0.5,
                },
              }}
            />
          </Box>
        )}

        {/* Unified annotation overlay */}
        {showTracks && view === 'video' && trackAnnotations.length > 0 && (
          <AnnotationViewer tracks={trackAnnotations} currentTime={progress} />
        )}

        {/* Active Species Overlay */}
        <CompactDetectionOverlay species={activeDetections} />

        {(!playing || showControls) && (
          <Tooltip
            title={playing ? t('video.pause') : t('video.play')}
            placement="top"
          >
            <IconButton
              aria-label={playing ? t('video.pause') : t('video.play')}
              onClick={(e) => {
                e.stopPropagation();
                togglePlayPause();
              }}
              sx={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                backgroundColor: 'rgba(0,0,0,0.3)',
                color: 'white',
                minWidth: 44,
                minHeight: 44,
                transition: 'all 0.2s ease-in-out',
                '&:hover': {
                  backgroundColor: 'rgba(0,0,0,0.5)',
                  transform: 'translate(-50%, -50%) scale(1.1)',
                },
                zIndex: 1,
              }}
            >
              {playing ? (
                <PauseIcon fontSize="medium" />
              ) : (
                <PlayArrowIcon fontSize="medium" />
              )}
            </IconButton>
          </Tooltip>
        )}

        {/* Playback speed + Fullscreen */}
        {view === 'video' && (!playing || showControls) && (
          <Box
            sx={{
              position: 'absolute',
              bottom: 8,
              right: 8,
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              zIndex: 1,
            }}
          >
            {SPEED_OPTIONS.map((speed) => (
              <Typography
                key={speed}
                component="button"
                role="button"
                title={`${t('video.speed')}: ${speed}×`}
                aria-label={`${t('video.speed')} ${speed}x`}
                aria-pressed={playbackRate === speed}
                onClick={(e) => {
                  e.stopPropagation();
                  setPlaybackRate(speed);
                }}
                sx={{
                  minWidth: 44,
                  minHeight: 44,
                  py: 0.5,
                  px: 1,
                  fontSize: '0.75rem',
                  fontWeight: playbackRate === speed ? 600 : 400,
                  color: 'white',
                  bgcolor:
                    playbackRate === speed
                      ? 'rgba(16, 185, 129, 0.5)'
                      : 'rgba(0,0,0,0.3)',
                  border: 'none',
                  borderRadius: 1,
                  cursor: 'pointer',
                  '&:hover': {
                    bgcolor:
                      playbackRate === speed
                        ? 'rgba(16, 185, 129, 0.6)'
                        : 'rgba(0,0,0,0.5)',
                  },
                }}
              >
                {speed}x
              </Typography>
            ))}
            <Tooltip title={t('video.fullscreen')} placement="top">
              <IconButton
                aria-label={t('video.fullscreen')}
                onClick={(e) => {
                  e.stopPropagation();
                  handleFullscreen();
                }}
                sx={{
                  backgroundColor: 'rgba(0,0,0,0.3)',
                  color: 'white',
                  minWidth: 44,
                  minHeight: 44,
                  '&:hover': {
                    backgroundColor: 'rgba(0,0,0,0.5)',
                  },
                }}
              >
                <FullscreenIcon />
              </IconButton>
            </Tooltip>
          </Box>
        )}

        <Box
          sx={{
            height: '100%',
            bgcolor: 'background.paper',
            display: view === 'video' ? 'block' : 'none',
            cursor: 'pointer',
          }}
          onClick={togglePlayPause}
        >
          <video
            ref={videoRef}
            src={`${BASE_API_URL}/videos/${video.id}/stream`}
            preload="auto"
            onTimeUpdate={(e) => handleProgress(e.currentTarget.currentTime)}
            onEnded={togglePlayPause}
            onError={(e) => {
              const el = e.currentTarget;
              const code = el.error?.code;
              const msg = el.error?.message;
              if (code != null || (msg && msg.length > 0)) {
                setError(
                  `${t('errors.loadVideo')} (${[code, msg].filter(Boolean).join(': ')})`,
                );
              } else {
                setError(t('errors.loadVideo'));
              }
            }}
            style={{ height: '100%', width: '100%', objectFit: 'contain' }}
            playsInline
            controls={false}
          />
        </Box>

        <Box
          sx={{
            height: '100%',
            bgcolor: 'background.paper',
            display: view === 'audio' ? 'block' : 'none',
          }}
        >
          {video.spectrogram_path && (
            <SpectrogramPlayer
              audioRef={videoRef}
              playing={playing}
              imageUrl={
                resolveImageUrl(video.spectrogram_path) ||
                `${BASE_URL}/${video.spectrogram_path}`.replace(/^\/{2,}/, '/')
              }
              detections={spectrogramDetections}
              visible={view === 'audio'}
            />
          )}
        </Box>
      </Box>

      {filteredDetections.length > 0 && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 1 }}
        >
          {t('video.timelineHint')}
        </Typography>
      )}
      {showTracksRegenHint && isAdmin && (
        <Typography
          variant="caption"
          color="text.secondary"
          sx={{ display: 'block', mt: 0.5 }}
        >
          {t('video.noTrackFramesHint')}
        </Typography>
      )}
      <ProgressBar
        duration={duration}
        progress={progress}
        detections={filteredDetections}
        onSeek={handleSeek}
      />
    </Box>
  );
};
