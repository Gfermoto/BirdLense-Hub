import { useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import FormControlLabel from '@mui/material/FormControlLabel';
import Alert from '@mui/material/Alert';
import Divider from '@mui/material/Divider';
import IconButton from '@mui/material/IconButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import ToggleButton from '@mui/material/ToggleButton';
import TuneIcon from '@mui/icons-material/Tune';
import CloseIcon from '@mui/icons-material/Close';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { fetchCameras } from '../../api/camerasHealth';
import { queryKeys } from '../../api/queryKeys';
import { PageHeader } from '../../components/PageHeader';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { useSettingsQuery } from '../../hooks/useSettingsQueries';
import { patchSettings } from '../../api/settingsSession';
import {
  fetchLiveRuntimeOverlays,
  LiveRuntimeOverlaysPayload,
} from '../../api/liveOverlays';

type StreamMode = 'go2rtc' | 'mjpeg';
type Point = [number, number];
type Polygon = Point[];
type EditorLayer = 'opencv_masks' | 'detector_zones';

function clamp01(v: number): number {
  if (v < 0) return 0;
  if (v > 1) return 1;
  return v;
}

function toNorm(value: number): number {
  return Math.round(clamp01(value) * 10000) / 10000;
}

function parseTriggerMasks(raw: unknown): Polygon[] {
  if (!Array.isArray(raw)) return [];
  const out: Polygon[] = [];
  raw.forEach((item) => {
    if (Array.isArray(item)) {
      const poly: Polygon = [];
      item.forEach((p) => {
        if (Array.isArray(p) && p.length >= 2) {
          const x = Number(p[0]);
          const y = Number(p[1]);
          if (Number.isFinite(x) && Number.isFinite(y)) {
            poly.push([toNorm(x), toNorm(y)]);
          }
        }
      });
      if (poly.length >= 3) out.push(poly);
      return;
    }
    if (typeof item === 'string') {
      const nums = item
        .split(/[\s,;]+/)
        .map((s) => s.trim())
        .filter(Boolean)
        .map((s) => Number(s))
        .filter((n) => Number.isFinite(n));
      if (nums.length >= 6 && nums.length % 2 === 0) {
        const poly: Polygon = [];
        for (let i = 0; i < nums.length; i += 2) {
          poly.push([toNorm(nums[i]), toNorm(nums[i + 1])]);
        }
        if (poly.length >= 3) out.push(poly);
      }
      return;
    }
    if (item && typeof item === 'object') {
      const coords = (item as { coordinates?: unknown }).coordinates;
      if (typeof coords === 'string') {
        out.push(...parseTriggerMasks([coords]));
      }
    }
  });
  return out;
}

function formatTriggerMasks(polygons: Polygon[]): string[] {
  return polygons.map((poly) =>
    poly.map(([x, y]) => `${toNorm(x)},${toNorm(y)}`).join(','),
  );
}

function parsePolygonList(raw: unknown): Polygon[] {
  if (!Array.isArray(raw)) return [];
  const out: Polygon[] = [];
  raw.forEach((poly) => {
    if (!Array.isArray(poly)) return;
    const pts: Polygon = [];
    poly.forEach((p) => {
      if (Array.isArray(p) && p.length >= 2) {
        const x = Number(p[0]);
        const y = Number(p[1]);
        if (Number.isFinite(x) && Number.isFinite(y)) {
          pts.push([toNorm(x), toNorm(y)]);
        }
      }
    });
    if (pts.length >= 3) out.push(pts);
  });
  return out;
}

function pointToSvg([x, y]: Point): string {
  return `${Math.round(x * 10000) / 100},${Math.round(y * 10000) / 100}`;
}

function OverlayPolygons({
  polygons,
  color,
  strokeWidth = 2,
}: {
  polygons: Polygon[];
  color: string;
  strokeWidth?: number;
}) {
  return (
    <>
      {polygons.map((poly, idx) => {
        const points = poly.map(pointToSvg).join(' ');
        return (
          <polygon
            key={`${color}-${idx}`}
            points={points}
            fill={`${color}44`}
            stroke={color}
            strokeWidth={strokeWidth}
            vectorEffect="non-scaling-stroke"
          />
        );
      })}
    </>
  );
}

function go2rtcMjpegPath(streamSrc: string): string {
  return `/go2rtc/api/stream.mjpeg?src=${encodeURIComponent(streamSrc)}`;
}

const FullscreenStream = ({
  streamSrc,
  streamUrlMjpeg,
  name,
  mode,
}: {
  streamSrc: string;
  streamUrlMjpeg?: string;
  name: string;
  mode: StreamMode;
}) => {
  const { t } = useTranslation();
  const [processorMjpegFailed, setProcessorMjpegFailed] = useState(false);
  const go2rtcSrc = streamSrc ? go2rtcMjpegPath(streamSrc) : '';
  const useProcessorMjpeg =
    mode === 'mjpeg' && Boolean(streamUrlMjpeg) && !processorMjpegFailed;
  const imgSrc = useProcessorMjpeg
    ? streamUrlMjpeg
    : go2rtcSrc || streamUrlMjpeg;
  if (!imgSrc) {
    return (
      <Box
        sx={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography color="text.secondary">{t('live.streamUnavailable')}</Typography>
      </Box>
    );
  }
  return (
    <Box
      component="img"
      src={imgSrc}
      alt={name}
      onError={() => {
        if (useProcessorMjpeg) {
          setProcessorMjpegFailed(true);
        }
      }}
      sx={{ width: '100%', height: '100%', objectFit: 'contain' }}
    />
  );
};

/** go2rtc MJPEG (без красного статуса WebRTC в iframe) или MJPEG процессора с запасным go2rtc. */
const CameraStream = ({
  streamSrc,
  streamUrlMjpeg,
  name,
  mode,
  onOpenEditor,
  canEdit,
}: {
  streamSrc: string;
  streamUrlMjpeg?: string;
  name: string;
  mode: StreamMode;
  onOpenEditor?: () => void;
  canEdit?: boolean;
}) => {
  const { t } = useTranslation();
  const [processorMjpegFailed, setProcessorMjpegFailed] = useState(false);
  const go2rtcSrc = streamSrc ? go2rtcMjpegPath(streamSrc) : '';
  const useProcessorMjpeg =
    mode === 'mjpeg' && Boolean(streamUrlMjpeg) && !processorMjpegFailed;
  const imgSrc = useProcessorMjpeg
    ? streamUrlMjpeg
    : go2rtcSrc || streamUrlMjpeg;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 280 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>{name}</span>
          {canEdit ? (
            <IconButton
              size="small"
              color="secondary"
              onClick={onOpenEditor}
              aria-label={t('live.openEditor')}
              title={t('live.openEditor')}
            >
              <TuneIcon fontSize="small" />
            </IconButton>
          ) : null}
        </Box>
      </Typography>
      {imgSrc ? (
        <Box
          component="img"
          src={imgSrc}
          alt={name}
          onError={() => {
            if (useProcessorMjpeg) {
              setProcessorMjpegFailed(true);
            }
          }}
          sx={{
            flex: 1,
            minHeight: 200,
            objectFit: 'contain',
            borderRadius: 1,
            bgcolor: 'black',
          }}
        />
      ) : (
        <Box
          sx={{
            flex: 1,
            minHeight: 200,
            borderRadius: 1,
            bgcolor: 'black',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Typography variant="body2" color="text.secondary">
            {t('live.streamUnavailable')}
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export const LivePage = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.liveView'));
  const [streamMode, setStreamMode] = useState<StreamMode>('go2rtc');
  const [fullscreenCamId, setFullscreenCamId] = useState<string | null>(null);
  const [editorLayer, setEditorLayer] = useState<EditorLayer>('opencv_masks');
  const [showOpencvMotion, setShowOpencvMotion] = useState(true);
  const [showYoloDetections, setShowYoloDetections] = useState(true);
  const [draftPolygons, setDraftPolygons] = useState<Polygon[]>([]);
  const [draftCurrent, setDraftCurrent] = useState<Polygon>([]);
  const { isAdmin } = useProtectedArea();
  const queryClient = useQueryClient();
  const { data: settings } = useSettingsQuery(isAdmin);
  const patchMutation = useMutation({
    mutationFn: patchSettings,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
    },
  });
  const {
    data: cameras,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.live.cameras,
    queryFn: fetchCameras,
  });

  const cams = cameras ?? [];
  const fullscreenCam = useMemo(
    () => cams.find((c) => c.id === fullscreenCamId) ?? null,
    [cams, fullscreenCamId],
  );
  const hasMjpeg = cams.some((c) => c.stream_url_mjpeg);
  const runtimeOverlaysQuery = useQuery<LiveRuntimeOverlaysPayload>({
    queryKey: queryKeys.live.overlays(fullscreenCamId || '__none__'),
    queryFn: () =>
      fetchLiveRuntimeOverlays({ cameraId: fullscreenCamId || '' }),
    enabled: Boolean(fullscreenCamId),
    refetchInterval: fullscreenCamId ? 2000 : false,
  });

  const getCameraLayerPolygons = (cameraId: string | null, layer: EditorLayer): Polygon[] => {
    const all = (
      (settings as { video?: { cameras?: Array<Record<string, unknown>> } } | undefined)
        ?.video?.cameras || []
    );
    const camera = all.find((c) => String(c.id || '') === String(cameraId || ''));
    const key = layer === 'detector_zones' ? 'detection_interest_zones' : 'opencv_masks';
    return parseTriggerMasks(camera?.[key]);
  };

  const opencvMotionPolygons = parsePolygonList(
    runtimeOverlaysQuery.data?.trigger_polygons,
  );
  const yoloDetectionPolygons = parsePolygonList(
    runtimeOverlaysQuery.data?.detector_polygons,
  );

  const onOverlayClick = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!isAdmin) return;
    const el = e.currentTarget;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const x = toNorm((e.clientX - rect.left) / rect.width);
    const y = toNorm((e.clientY - rect.top) / rect.height);
    setDraftCurrent((prev) => [...prev, [x, y]]);
  };

  const closeCurrentPolygon = () => {
    if (draftCurrent.length < 3) return;
    setDraftPolygons((prev) => [...prev, draftCurrent]);
    setDraftCurrent([]);
  };

  const removeMaskAt = (index: number) => {
    setDraftPolygons((prev) => prev.filter((_, i) => i !== index));
  };

  const switchEditorLayer = (next: EditorLayer) => {
    setEditorLayer(next);
    setDraftPolygons(getCameraLayerPolygons(fullscreenCamId, next));
    setDraftCurrent([]);
  };

  const savePolygons = async () => {
    if (!fullscreenCamId) return;
    const polygonsToSave = [...draftPolygons];
    const isDetectorZones = editorLayer === 'detector_zones';
    const all = (
      (settings as { video?: { cameras?: Array<Record<string, unknown>> } } | undefined)
        ?.video?.cameras || []
    ).map((camera) => {
      const id = String(camera.id || '');
      if (id !== String(fullscreenCamId)) {
        return camera;
      }
      return {
        ...camera,
        ...(isDetectorZones
          ? {
              detection_interest_zones: polygonsToSave,
              detection_interest_zones_required: polygonsToSave.length > 0,
            }
          : {
              opencv_masks: formatTriggerMasks(polygonsToSave),
            }),
      };
    });
    await patchMutation.mutateAsync({
      video: { cameras: all },
    });
  };

  const numCols =
    cams.length <= 1 ? 1 : cams.length <= 2 ? 2 : cams.length <= 4 ? 4 : 6;
  const gridSize = 12 / numCols;

  if (isLoading) {
    return <PageLoadingState label={t('live.loading')} />;
  }

  if (error) {
    return (
      <PageMessageState
        title={t('nav.liveView')}
        message={t('live.errorLoad')}
        severity="error"
        action={
          <Button variant="outlined" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }

  return (
    <Box>
      <PageHeader
        title={t('live.title')}
        description={t('live.streamTitle')}
        actions={
          hasMjpeg ? (
            <ToggleButtonGroup
              value={streamMode}
              exclusive
              onChange={(_, v: StreamMode | null) =>
                v != null && setStreamMode(v)
              }
              size="medium"
              aria-label={t('live.streamModeAria')}
              sx={{
                '& .MuiToggleButton-root': { minHeight: 40, px: 1.75 },
              }}
            >
              <ToggleButton value="go2rtc">{t('live.modeGo2rtc')}</ToggleButton>
              <ToggleButton value="mjpeg">{t('live.modeMjpeg')}</ToggleButton>
            </ToggleButtonGroup>
          ) : null
        }
        sx={{ mb: 3 }}
      />
      {cams.length === 0 ? (
        <PageMessageState message={t('live.noCameras')} />
      ) : (
        <Grid container spacing={2}>
          {cams.map((cam) => (
            <Grid key={cam.id} size={{ xs: 12, sm: 6, md: gridSize }}>
              <CameraStream
                key={`${cam.id}-${streamMode}`}
                streamSrc={cam.id}
                streamUrlMjpeg={cam.stream_url_mjpeg}
                name={cam.name}
                mode={streamMode}
                canEdit={isAdmin}
                onOpenEditor={() => {
                  const initialMasks = getCameraLayerPolygons(cam.id, 'opencv_masks');
                  setFullscreenCamId(cam.id);
                  setEditorLayer('opencv_masks');
                  setDraftPolygons(initialMasks.map((poly) => [...poly]));
                  setDraftCurrent([]);
                }}
              />
            </Grid>
          ))}
        </Grid>
      )}
      <Dialog
        open={!!fullscreenCam && isAdmin}
        onClose={() => setFullscreenCamId(null)}
        fullScreen
      >
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>
            {t('live.editorTitle', { name: fullscreenCam?.name ?? '' })}
          </span>
          <IconButton
            onClick={() => setFullscreenCamId(null)}
            aria-label={t('live.exitFullscreen')}
          >
            <CloseIcon />
          </IconButton>
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 340px' }, minHeight: 'calc(100vh - 120px)' }}>
            <Box
              sx={{
                position: 'relative',
                bgcolor: 'black',
                minHeight: 420,
                cursor: isAdmin ? 'crosshair' : 'default',
              }}
            >
              {fullscreenCam ? (
                <FullscreenStream
                  streamSrc={fullscreenCam.id}
                  streamUrlMjpeg={fullscreenCam.stream_url_mjpeg}
                  name={fullscreenCam.name}
                  mode={streamMode}
                />
              ) : null}
              <Box
                component="svg"
                viewBox="0 0 100 100"
                preserveAspectRatio="none"
                onClick={onOverlayClick}
                sx={{
                  position: 'absolute',
                  inset: 0,
                  width: '100%',
                  height: '100%',
                  pointerEvents: isAdmin ? 'auto' : 'none',
                }}
              >
                <OverlayPolygons
                  polygons={draftPolygons}
                  color={editorLayer === 'detector_zones' ? '#03a9f4' : '#ff5252'}
                />
                {showOpencvMotion ? (
                  <OverlayPolygons
                    polygons={opencvMotionPolygons}
                    color="#ffb300"
                    strokeWidth={3}
                  />
                ) : null}
                {showYoloDetections ? (
                  <OverlayPolygons
                    polygons={yoloDetectionPolygons}
                    color="#00c853"
                  />
                ) : null}
                {draftCurrent.length > 1 ? (
                  <polyline
                    points={draftCurrent.map(pointToSvg).join(' ')}
                    fill="none"
                    stroke={editorLayer === 'detector_zones' ? '#03a9f4' : '#ff5252'}
                    strokeWidth={2}
                    strokeDasharray="4 3"
                  />
                ) : null}
                {draftCurrent.map(([x, y], idx) => (
                  <circle
                    key={`p-${idx}`}
                    cx={Math.round(x * 10000) / 100}
                    cy={Math.round(y * 10000) / 100}
                    r="0.8"
                    fill={editorLayer === 'detector_zones' ? '#03a9f4' : '#ff5252'}
                  />
                ))}
              </Box>
            </Box>
            <Box sx={{ p: 2, borderLeft: { md: '1px solid' }, borderColor: 'divider' }}>
              <Stack spacing={1.5}>
                <Typography variant="overline" color="text.secondary">
                  {t('live.overlaysSection')}
                </Typography>
                <FormControlLabel
                  control={
                    <Switch
                      checked={showOpencvMotion}
                      onChange={(e) => setShowOpencvMotion(e.target.checked)}
                    />
                  }
                  label={t('live.showOpencvMotion')}
                />
                <FormControlLabel
                  control={
                    <Switch
                      checked={showYoloDetections}
                      onChange={(e) => setShowYoloDetections(e.target.checked)}
                    />
                  }
                  label={t('live.showYoloDetections')}
                />
                <Typography variant="caption" color="text.secondary" display="block">
                  {t('live.overlaysHint')}
                </Typography>
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                  {t('live.overlaysHowTo')}
                </Typography>
                {showOpencvMotion && runtimeOverlaysQuery.data?.opencv_last_decision_reason ? (
                  <Typography variant="caption" color="text.secondary" display="block">
                    OpenCV: {runtimeOverlaysQuery.data.opencv_last_decision_reason}
                    {opencvMotionPolygons.length === 0
                      ? ` — ${t('live.opencvNoContours')}`
                      : ` — ${t('live.opencvContourCount', { count: opencvMotionPolygons.length })}`}
                  </Typography>
                ) : null}
                {runtimeOverlaysQuery.isError ? (
                  <Alert severity="warning" variant="outlined">
                    {t('live.overlayLoadFailed')}
                  </Alert>
                ) : null}
                {!runtimeOverlaysQuery.isError &&
                showOpencvMotion &&
                runtimeOverlaysQuery.isSuccess &&
                runtimeOverlaysQuery.data?.source === 'none' ? (
                  <Typography variant="caption" color="text.secondary" display="block">
                    {t('live.overlayNoProcessorData')}
                  </Typography>
                ) : null}

                <Divider sx={{ my: 0.5 }} />
                <Typography variant="overline" color="text.secondary">
                  {t('live.masksSection')}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {editorLayer === 'detector_zones' ? t('live.detectorZonesHint') : t('live.masksHint')}
                </Typography>
                <ToggleButtonGroup
                  value={editorLayer}
                  exclusive
                  onChange={(_, v: EditorLayer | null) => v && switchEditorLayer(v)}
                  size="small"
                >
                  <ToggleButton value="opencv_masks">{t('live.layerTriggerMask')}</ToggleButton>
                  <ToggleButton value="detector_zones">{t('live.layerDetectorZone')}</ToggleButton>
                </ToggleButtonGroup>
                {draftPolygons.length > 0 ? (
                  <Stack spacing={0.5}>
                    {draftPolygons.map((poly, idx) => (
                      <Stack
                        key={`mask-${idx}`}
                        direction="row"
                        alignItems="center"
                        justifyContent="space-between"
                        spacing={1}
                      >
                        <Typography variant="caption" color="text.secondary">
                          {t('live.maskItem', { n: idx + 1, points: poly.length })}
                        </Typography>
                        <Button
                          size="small"
                          color="error"
                          variant="text"
                          onClick={() => removeMaskAt(idx)}
                          disabled={!isAdmin}
                        >
                          {t('live.deleteMask')}
                        </Button>
                      </Stack>
                    ))}
                  </Stack>
                ) : (
                  <Typography variant="caption" color="text.secondary">
                    {t('live.noMasksYet')}
                  </Typography>
                )}
                <Stack direction="row" spacing={1}>
                  <Button
                    variant="outlined"
                    onClick={closeCurrentPolygon}
                    disabled={!isAdmin || draftCurrent.length < 3}
                  >
                    {t('live.closePolygon')}
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={() => setDraftCurrent((prev) => prev.slice(0, -1))}
                    disabled={!isAdmin || draftCurrent.length === 0}
                  >
                    {t('live.undoPoint')}
                  </Button>
                </Stack>
                <Stack direction="row" spacing={1}>
                  <Button
                    variant="outlined"
                    color="warning"
                    onClick={() => {
                      setDraftPolygons([]);
                      setDraftCurrent([]);
                    }}
                    disabled={!isAdmin}
                  >
                    {t('live.clearLayer')}
                  </Button>
                  <Button
                    variant="contained"
                    onClick={savePolygons}
                    disabled={!isAdmin || patchMutation.isPending || draftCurrent.length > 0}
                  >
                    {t('live.saveLayer')}
                  </Button>
                </Stack>
                {patchMutation.isError ? (
                  <Alert severity="error" variant="outlined">
                    {t('live.saveFailed')}
                  </Alert>
                ) : null}
                {patchMutation.isSuccess ? (
                  <Alert severity="success" variant="outlined">
                    {t('live.saveOk')}
                  </Alert>
                ) : null}
              </Stack>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button
            variant="outlined"
            startIcon={<CloseIcon />}
            onClick={() => setFullscreenCamId(null)}
          >
            {t('live.exitFullscreen')}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
