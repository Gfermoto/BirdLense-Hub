import { useMemo, useRef, useState } from 'react';
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
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import FullscreenIcon from '@mui/icons-material/Fullscreen';
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

type StreamMode = 'go2rtc' | 'mjpeg';
type OverlayLayer = 'masks' | 'triggerRegions' | 'detectorRegions';
type Point = [number, number];
type Polygon = Point[];

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

function formatTriggerMasks(polygons: Polygon[]): string[] {
  return polygons.map((poly) =>
    poly.map(([x, y]) => `${toNorm(x)},${toNorm(y)}`).join(','),
  );
}

function pointToSvg([x, y]: Point): string {
  return `${Math.round(x * 10000) / 100},${Math.round(y * 10000) / 100}`;
}

function OverlayPolygons({
  polygons,
  color,
}: {
  polygons: Polygon[];
  color: string;
}) {
  return (
    <>
      {polygons.map((poly, idx) => {
        const points = poly.map(pointToSvg).join(' ');
        return (
          <polygon
            key={`${color}-${idx}`}
            points={points}
            fill={`${color}33`}
            stroke={color}
            strokeWidth={2}
          />
        );
      })}
    </>
  );
}

/** Go2RTC iframe (RTC/MSE) или MJPEG img — fallback при 502/go2rtc недоступен. */
const CameraStream = ({
  streamUrl,
  streamUrlMjpeg,
  name,
  mode,
  onFullscreen,
  canFullscreen,
}: {
  streamUrl: string;
  streamUrlMjpeg?: string;
  name: string;
  mode: StreamMode;
  onFullscreen?: () => void;
  canFullscreen?: boolean;
}) => {
  const useMjpeg = mode === 'mjpeg' && streamUrlMjpeg;
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: 280 }}>
      <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span>{name}</span>
          {canFullscreen ? (
            <IconButton
              size="small"
              onClick={onFullscreen}
              title="Развернуть и настроить"
            >
              <FullscreenIcon fontSize="small" />
            </IconButton>
          ) : null}
        </Box>
      </Typography>
      {useMjpeg ? (
        <Box
          component="img"
          src={streamUrlMjpeg}
          alt={name}
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
          component="iframe"
          src={streamUrl}
          title={name}
          sx={{
            flex: 1,
            minHeight: 200,
            border: 'none',
            borderRadius: 1,
            bgcolor: 'black',
          }}
        />
      )}
    </Box>
  );
};

export const LivePage = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.liveView'));
  const [streamMode, setStreamMode] = useState<StreamMode>('go2rtc');
  const [fullscreenCamId, setFullscreenCamId] = useState<string | null>(null);
  const [showMasks, setShowMasks] = useState(true);
  const [showTriggerRegions, setShowTriggerRegions] = useState(true);
  const [showDetectorRegions, setShowDetectorRegions] = useState(true);
  const [editLayer, setEditLayer] = useState<OverlayLayer>('masks');
  const [draftPolygons, setDraftPolygons] = useState<Polygon[]>([]);
  const [draftCurrent, setDraftCurrent] = useState<Polygon>([]);
  const overlayRef = useRef<HTMLDivElement | null>(null);
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

  const cams = cameras ?? [];
  const fullscreenCam = useMemo(
    () => cams.find((c) => c.id === fullscreenCamId) ?? null,
    [cams, fullscreenCamId],
  );
  const hasMjpeg = cams.some((c) => c.stream_url_mjpeg);

  const triggerMasks: Polygon[] = useMemo(() => {
    const raw = (settings as { triggers?: { opencv?: { masks?: unknown } } } | undefined)
      ?.triggers?.opencv?.masks;
    return parseTriggerMasks(raw);
  }, [settings]);
  const detectorMasks: Polygon[] = useMemo(() => {
    const raw = (settings as { processor?: { detection_ignore_masks?: unknown } } | undefined)
      ?.processor?.detection_ignore_masks;
    return parsePolygonList(raw);
  }, [settings]);
  const detectorRegions: Polygon[] = useMemo(() => {
    const raw = (settings as { processor?: { detection_interest_zones?: unknown } } | undefined)
      ?.processor?.detection_interest_zones;
    return parsePolygonList(raw);
  }, [settings]);

  const activeLayerPolygons =
    editLayer === 'masks'
      ? detectorMasks
      : editLayer === 'triggerRegions'
        ? triggerMasks
        : detectorRegions;

  const beginEditLayer = (layer: OverlayLayer) => {
    setEditLayer(layer);
    const src =
      layer === 'masks'
        ? detectorMasks
        : layer === 'triggerRegions'
          ? triggerMasks
          : detectorRegions;
    setDraftPolygons(src.map((poly) => [...poly]));
    setDraftCurrent([]);
  };

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

  const savePolygons = async () => {
    const polygonsToSave = [...draftPolygons];
    if (editLayer === 'masks') {
      await patchMutation.mutateAsync({
        processor: { detection_ignore_masks: polygonsToSave },
      });
      return;
    }
    if (editLayer === 'detectorRegions') {
      await patchMutation.mutateAsync({
        processor: { detection_interest_zones: polygonsToSave },
      });
      return;
    }
    await patchMutation.mutateAsync({
      triggers: { opencv: { masks: formatTriggerMasks(polygonsToSave) } },
    });
  };

  // Адаптивная сетка: 1 камера — на всю ширину, 2 — в 2 колонки, 3–4 — в 4, 5+ — в 6
  const numCols =
    cams.length <= 1 ? 1 : cams.length <= 2 ? 2 : cams.length <= 4 ? 4 : 6;
  const gridSize = 12 / numCols;

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
                streamUrl={cam.stream_url}
                streamUrlMjpeg={cam.stream_url_mjpeg}
                name={cam.name}
                mode={streamMode}
                canFullscreen={isAdmin}
                onFullscreen={() => {
                  setFullscreenCamId(cam.id);
                  beginEditLayer('masks');
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
        <DialogTitle>
          {fullscreenCam?.name ?? 'Камера'} — Live Editor
        </DialogTitle>
        <DialogContent sx={{ p: 0 }}>
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 340px' }, minHeight: 'calc(100vh - 120px)' }}>
            <Box
              ref={overlayRef}
              sx={{
                position: 'relative',
                bgcolor: 'black',
                minHeight: 420,
                cursor: isAdmin ? 'crosshair' : 'default',
              }}
            >
              {fullscreenCam ? (
                streamMode === 'mjpeg' && fullscreenCam.stream_url_mjpeg ? (
                  <Box
                    component="img"
                    src={fullscreenCam.stream_url_mjpeg}
                    alt={fullscreenCam.name}
                    sx={{ width: '100%', height: '100%', objectFit: 'contain' }}
                  />
                ) : (
                  <Box
                    component="iframe"
                    src={fullscreenCam.stream_url}
                    title={fullscreenCam.name}
                    sx={{ width: '100%', height: '100%', border: 'none' }}
                  />
                )
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
                {showMasks ? <OverlayPolygons polygons={detectorMasks} color="#ff5252" /> : null}
                {showTriggerRegions ? <OverlayPolygons polygons={triggerMasks} color="#ffb300" /> : null}
                {showDetectorRegions ? <OverlayPolygons polygons={detectorRegions} color="#00c853" /> : null}
                <OverlayPolygons polygons={draftPolygons} color="#40c4ff" />
                {draftCurrent.length > 1 ? (
                  <polyline
                    points={draftCurrent.map(pointToSvg).join(' ')}
                    fill="none"
                    stroke="#40c4ff"
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
                    fill="#40c4ff"
                  />
                ))}
              </Box>
            </Box>
            <Box sx={{ p: 2, borderLeft: { md: '1px solid' }, borderColor: 'divider' }}>
              <Stack spacing={1}>
                <FormControlLabel
                  control={<Switch checked={showMasks} onChange={(e) => setShowMasks(e.target.checked)} />}
                  label="Показать маски"
                />
                <FormControlLabel
                  control={<Switch checked={showTriggerRegions} onChange={(e) => setShowTriggerRegions(e.target.checked)} />}
                  label="Показать регионы триггера"
                />
                <FormControlLabel
                  control={<Switch checked={showDetectorRegions} onChange={(e) => setShowDetectorRegions(e.target.checked)} />}
                  label="Показать регионы детектора"
                />
                <Divider sx={{ my: 1 }} />
                <ToggleButtonGroup
                  value={editLayer}
                  exclusive
                  onChange={(_, v: OverlayLayer | null) => v && beginEditLayer(v)}
                  size="small"
                  fullWidth
                >
                  <ToggleButton value="masks">Маски</ToggleButton>
                  <ToggleButton value="triggerRegions">Триггер</ToggleButton>
                  <ToggleButton value="detectorRegions">Детектор</ToggleButton>
                </ToggleButtonGroup>
                <Alert severity="info" variant="outlined">
                  Редактор доступен только администратору. Клик по видео добавляет точку.
                </Alert>
                <Stack direction="row" spacing={1}>
                  <Button
                    variant="outlined"
                    onClick={closeCurrentPolygon}
                    disabled={!isAdmin || draftCurrent.length < 3}
                  >
                    Замкнуть полигон
                  </Button>
                  <Button
                    variant="outlined"
                    onClick={() => setDraftCurrent((prev) => prev.slice(0, -1))}
                    disabled={!isAdmin || draftCurrent.length === 0}
                  >
                    Отменить точку
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
                    Очистить слой
                  </Button>
                  <Button
                    variant="contained"
                    onClick={savePolygons}
                    disabled={!isAdmin || patchMutation.isPending || draftCurrent.length > 0}
                  >
                    Сохранить
                  </Button>
                </Stack>
                {patchMutation.isError ? (
                  <Alert severity="error" variant="outlined">
                    Не удалось сохранить изменения.
                  </Alert>
                ) : null}
                {patchMutation.isSuccess ? (
                  <Alert severity="success" variant="outlined">
                    Слой сохранен.
                  </Alert>
                ) : null}
                <Typography variant="caption" color="text.secondary">
                  Активный слой: {editLayer}. Полигонов: {activeLayerPolygons.length}. Черновик: {draftPolygons.length}.
                </Typography>
              </Stack>
            </Box>
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFullscreenCamId(null)}>Закрыть</Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};
