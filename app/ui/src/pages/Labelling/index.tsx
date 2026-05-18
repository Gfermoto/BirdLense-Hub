import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  LinearProgress,
  MenuItem,
  Select,
  Stack,
  Tooltip,
  Typography,
} from '@mui/material';
import { useTranslation } from 'react-i18next';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { PageHeader } from '../../components/PageHeader';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import {
  useExportLabellingCasesMutation,
  useLabellingCasesQuery,
  useLabellingFeedbackMutation,
  useMineLabellingCasesMutation,
  usePatchLabellingCaseMutation,
} from '../../hooks/useLabellingQueries';
import type { LabellingCase, LabellingCaseStatus } from '../../api/labelling';

type FilterStatus = LabellingCaseStatus | 'all';
type ViewMode = 'snapshot' | 'video';
type WorkflowFilter = 'all' | 'new' | 'error';

const statusColor: Record<LabellingCaseStatus, 'default' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
};

function formatCaseStatus(status: LabellingCaseStatus, t: (key: string) => string): string {
  if (status === 'pending') return t('labelling.status.pending');
  if (status === 'approved') return t('labelling.status.approved');
  return t('labelling.status.rejected');
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  return target.isContentEditable;
}

function colorForCase(item: LabellingCase): string {
  if (item.status === 'approved') return '#22c55e';
  if (item.status === 'rejected') return '#9ca3af';
  return '#eab308';
}

function buildOverlayBoxes(item: LabellingCase, t: (key: string) => string) {
  const fallbackBox = Array.isArray(item.bbox) && item.bbox.length === 4 ? item.bbox : null;
  const fromFrames = (item.track_frames || []).filter(
    (row) => Array.isArray(row.bbox) && row.bbox.length === 4,
  );
  const base = fallbackBox ? [{ bbox: fallbackBox, t: null }] : [];
  const frames = fromFrames.length > 0 ? fromFrames : base;
  return {
    hasGeometry: frames.length > 0,
    getCurrentBoxes(currentTime: number | null) {
      const currentFrame =
        currentTime == null
          ? frames[0]
          : [...frames].sort(
              (a, b) => Math.abs((a.t ?? 0) - currentTime) - Math.abs((b.t ?? 0) - currentTime),
            )[0];
      if (!currentFrame || !Array.isArray(currentFrame.bbox)) return [];
      const bbox = currentFrame.bbox as number[];
      const boxes: Array<{
        bbox: number[];
        color: string;
        dashed?: boolean;
        label: string;
      }> = [];
      if (item.status === 'rejected') {
        boxes.push({
          bbox,
          color: '#9ca3af',
          dashed: true,
          label: t('labelling.box.rejected'),
        });
        return boxes;
      }
      if (item.behavior_label) {
        boxes.push({
          bbox,
          color: '#eab308',
          label: `${t('labelling.box.main')}: ${item.behavior_label}${
            item.behavior_confidence != null ? ` (${Math.round(item.behavior_confidence * 100)}%)` : ''
          }`,
        });
      }
      if (item.behavior_shadow_label) {
        boxes.push({
          bbox,
          color: '#a855f7',
          dashed: true,
          label: `${t('labelling.box.shadow')}: ${item.behavior_shadow_label}${
            item.behavior_shadow_confidence != null ? ` (${Math.round(item.behavior_shadow_confidence * 100)}%)` : ''
          }`,
        });
      }
      if (item.status === 'approved') {
        boxes.push({
          bbox,
          color: '#22c55e',
          label: t('labelling.box.groundTruth'),
        });
      }
      if (boxes.length === 0) {
        boxes.push({
          bbox,
          color: colorForCase(item),
          label: item.species_name || t('labelling.box.detection'),
        });
      }
      return boxes;
    },
  };
}

const LabellingMediaOverlay: React.FC<{ item: LabellingCase; viewMode: ViewMode }> = ({ item, viewMode }) => {
  const { t } = useTranslation();
  const videoRef = React.useRef<HTMLVideoElement | null>(null);
  const canvasRef = React.useRef<HTMLCanvasElement | null>(null);
  const containerRef = React.useRef<HTMLDivElement | null>(null);
  const overlay = React.useMemo(() => buildOverlayBoxes(item, t), [item, t]);

  React.useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;
    const resize = () => {
      const rect = container.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width));
      canvas.height = Math.max(1, Math.floor(rect.height));
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(container);
    return () => ro.disconnect();
  }, []);

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const firstT = item.track_frames?.[0]?.t;
    if (viewMode === 'snapshot') {
      const seekAndPause = () => {
        if (typeof firstT === 'number' && Number.isFinite(firstT)) {
          video.currentTime = Math.max(0, firstT);
        }
        void video.pause();
      };
      video.addEventListener('loadedmetadata', seekAndPause, { once: true });
      seekAndPause();
      return () => video.removeEventListener('loadedmetadata', seekAndPause);
    }
    return undefined;
  }, [item.track_frames, viewMode]);

  React.useEffect(() => {
    let raf = 0;
    const draw = () => {
      const canvas = canvasRef.current;
      const video = videoRef.current;
      if (!canvas || !video) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      const currentTime = viewMode === 'snapshot' ? item.track_frames?.[0]?.t ?? null : video.currentTime;
      const boxes = overlay.getCurrentBoxes(currentTime ?? null);
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const box of boxes) {
        const [x, y, w, h] = box.bbox;
        const bx = x * canvas.width;
        const by = y * canvas.height;
        const bw = w * canvas.width;
        const bh = h * canvas.height;
        ctx.save();
        ctx.strokeStyle = box.color;
        ctx.lineWidth = 2;
        if (box.dashed) ctx.setLineDash([8, 4]);
        ctx.strokeRect(bx, by, bw, bh);
        ctx.font = '12px sans-serif';
        const label = box.label;
        const textW = Math.ceil(ctx.measureText(label).width + 8);
        ctx.fillStyle = box.color;
        ctx.fillRect(bx, Math.max(0, by - 18), textW, 16);
        ctx.fillStyle = '#111';
        ctx.fillText(label, bx + 4, Math.max(12, by - 6));
        ctx.restore();
      }
      raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(raf);
  }, [item.track_frames, overlay, viewMode]);

  if (!overlay.hasGeometry) {
    return <Alert severity="warning">{t('labelling.media.noOverlayData')}</Alert>;
  }
  if (!item.video_stream_url) {
    return <Alert severity="warning">{t('labelling.media.noMedia')}</Alert>;
  }

  return (
    <Box ref={containerRef} sx={{ position: 'relative', width: '100%', maxHeight: 420, aspectRatio: '16 / 9' }}>
      <Box
        component="video"
        ref={videoRef}
        controls={viewMode === 'video'}
        autoPlay={viewMode === 'video'}
        muted
        preload="metadata"
        sx={{ width: '100%', height: '100%', borderRadius: 1, objectFit: 'contain', bgcolor: '#000' }}
        src={item.video_stream_url}
      />
      <Box
        ref={canvasRef}
        component="canvas"
        sx={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}
      />
    </Box>
  );
};

export const LabellingPage: React.FC = () => {
  const { t, i18n } = useTranslation();
  useDocumentTitle(t('labelling.title'));
  const [status, setStatus] = React.useState<FilterStatus>('all');
  const [workflowFilter, setWorkflowFilter] = React.useState<WorkflowFilter>('all');
  const [cameraFilter, setCameraFilter] = React.useState<string>('all');
  const [viewMode, setViewMode] = React.useState<ViewMode>('snapshot');
  const [exportFormat, setExportFormat] = React.useState<'yolo' | 'coco'>('yolo');
  const [currentIndex, setCurrentIndex] = React.useState(0);
  const q = useLabellingCasesQuery('all', 500);
  const mine = useMineLabellingCasesMutation();
  const patch = usePatchLabellingCaseMutation();
  const feedback = useLabellingFeedbackMutation();
  const exp = useExportLabellingCasesMutation();
  const [behaviorTag, setBehaviorTag] = React.useState('feeding');
  const [speciesTag, setSpeciesTag] = React.useState('');
  const [showHelp, setShowHelp] = React.useState<boolean>(() => localStorage.getItem('labelling_help_seen') !== '1');

  const allItems = q.data?.items || [];
  const cameras = React.useMemo(
    () => Array.from(new Set(allItems.map((x) => x.camera_id).filter((x): x is string => Boolean(x)))).sort(),
    [allItems],
  );
  const items = React.useMemo(() => {
    const filtered = allItems.filter((item) => {
      if (status !== 'all' && item.status !== status) return false;
      if (workflowFilter === 'new' && item.status !== 'pending') return false;
      if (workflowFilter === 'error' && !(item.reason_code.includes('blind') || item.reason_code.includes('fallback')))
        return false;
      if (cameraFilter !== 'all' && item.camera_id !== cameraFilter) return false;
      return true;
    });
    const priorityScore = (item: LabellingCase) => {
      if (item.reason_code.includes('blind')) return 0;
      if (item.reason_code.includes('fallback')) return 1;
      if (item.status === 'pending') return 2;
      return 3;
    };
    return filtered.sort((a, b) => {
      const pa = priorityScore(a);
      const pb = priorityScore(b);
      if (pa !== pb) return pa - pb;
      return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    });
  }, [allItems, cameraFilter, status, workflowFilter]);

  React.useEffect(() => {
    if (currentIndex >= items.length) setCurrentIndex(Math.max(0, items.length - 1));
  }, [currentIndex, items.length]);

  const current = items[currentIndex] || null;
  const reviewed = items.filter((x) => x.status !== 'pending').length;
  const progress = items.length > 0 ? (reviewed / items.length) * 100 : 0;

  const gotoNext = React.useCallback(() => setCurrentIndex((v) => Math.min(items.length - 1, v + 1)), [items.length]);
  const gotoPrev = React.useCallback(() => setCurrentIndex((v) => Math.max(0, v - 1)), []);
  const doConfirm = React.useCallback(() => {
    if (!current) return;
    feedback.mutate({ id: current.id, action: 'confirm_behavior', behavior_tag: behaviorTag });
  }, [behaviorTag, current, feedback]);
  const doReject = React.useCallback(() => {
    if (!current) return;
    feedback.mutate({ id: current.id, action: 'reject_box' });
  }, [current, feedback]);

  React.useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target)) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        doConfirm();
      } else if (e.key === 'Escape' || e.key === 'Backspace') {
        e.preventDefault();
        doReject();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        gotoNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        gotoPrev();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [doConfirm, doReject, gotoNext, gotoPrev]);

  return (
    <ProtectedRoute title={t('labelling.title')} requireAdmin={false}>
      <Stack spacing={2}>
        <PageHeader
          title={t('labelling.title')}
          description={t('labelling.description')}
          titleVariant="h4"
        />
        <Card>
          <CardContent>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }}>
              <Button
                variant="contained"
                onClick={() => mine.mutate({ lookback_hours: 72, max_rows: 500 })}
                disabled={mine.isPending}
              >
                {t('labelling.actions.runMiner')}
              </Button>
              <FormControl size="small" sx={{ minWidth: 140 }}>
                <InputLabel id="labelling-lang-label">{t('labelling.language')}</InputLabel>
                <Select
                  labelId="labelling-lang-label"
                  value={i18n.language.startsWith('ru') ? 'ru' : 'en'}
                  label={t('labelling.language')}
                  onChange={(e) => void i18n.changeLanguage(String(e.target.value))}
                >
                  <MenuItem value="ru">RU</MenuItem>
                  <MenuItem value="en">EN</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="labelling-status-label">{t('labelling.filters.status')}</InputLabel>
                <Select
                  labelId="labelling-status-label"
                  value={status}
                  label={t('labelling.filters.status')}
                  onChange={(e) => setStatus(e.target.value as FilterStatus)}
                >
                  <MenuItem value="all">{t('labelling.filters.all')}</MenuItem>
                  <MenuItem value="pending">{t('labelling.status.pending')}</MenuItem>
                  <MenuItem value="approved">{t('labelling.status.approved')}</MenuItem>
                  <MenuItem value="rejected">{t('labelling.status.rejected')}</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="labelling-workflow-label">{t('labelling.filters.workflow')}</InputLabel>
                <Select
                  labelId="labelling-workflow-label"
                  value={workflowFilter}
                  label={t('labelling.filters.workflow')}
                  onChange={(e) => setWorkflowFilter(e.target.value as WorkflowFilter)}
                >
                  <MenuItem value="all">{t('labelling.filters.all')}</MenuItem>
                  <MenuItem value="new">{t('labelling.filters.onlyNew')}</MenuItem>
                  <MenuItem value="error">{t('labelling.filters.onlyError')}</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="labelling-camera-label">{t('labelling.filters.camera')}</InputLabel>
                <Select
                  labelId="labelling-camera-label"
                  value={cameraFilter}
                  label={t('labelling.filters.camera')}
                  onChange={(e) => setCameraFilter(String(e.target.value))}
                >
                  <MenuItem value="all">{t('labelling.filters.all')}</MenuItem>
                  {cameras.map((cam) => (
                    <MenuItem key={cam} value={cam}>
                      {cam}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="labelling-export-label">{t('labelling.export.title')}</InputLabel>
                <Select
                  labelId="labelling-export-label"
                  value={exportFormat}
                  label={t('labelling.export.title')}
                  onChange={(e) => setExportFormat(e.target.value as 'yolo' | 'coco')}
                >
                  <MenuItem value="yolo">YOLO</MenuItem>
                  <MenuItem value="coco">COCO</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="outlined"
                onClick={() => exp.mutate({ format: exportFormat, status: 'approved' })}
                disabled={exp.isPending}
              >
                {t('labelling.export.approved')}
              </Button>
            </Stack>
            <Stack spacing={0.5} sx={{ mt: 1.5 }}>
              <Typography variant="body2">
                {t('labelling.progressLabel', { done: reviewed, total: items.length })}
              </Typography>
              <LinearProgress variant="determinate" value={progress} />
            </Stack>
            {mine.data ? (
              <Alert sx={{ mt: 1.5 }} severity="info">
                {t('labelling.minerResult', { created: mine.data.created, skipped: mine.data.skipped })}
              </Alert>
            ) : null}
            {exp.data ? (
              <Alert sx={{ mt: 1.5 }} severity="success">
                {t('labelling.exportDone', { format: exp.data.format, version: exp.data.version, path: exp.data.path })}
              </Alert>
            ) : null}
          </CardContent>
        </Card>
        <Stack spacing={1.5}>
          {q.isLoading ? <Alert severity="info">{t('labelling.states.loading')}</Alert> : null}
          {q.isError ? (
            <Alert severity="error">{t('labelling.states.error')}</Alert>
          ) : null}
          {current ? (
            <Card>
              <CardContent>
                <Stack spacing={1.5}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="h6">
                      {t('labelling.caseTitle', { id: current.id })}
                    </Typography>
                    <Chip size="small" label={formatCaseStatus(current.status, t)} color={statusColor[current.status]} />
                    <Chip size="small" label={current.reason_code} />
                    {current.species_name ? <Chip size="small" label={current.species_name} variant="outlined" /> : null}
                  </Stack>
                  <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                    <Typography variant="body1">
                      <strong>{t('labelling.meta.camera')}:</strong> {current.camera_id || '-'}
                    </Typography>
                    <Typography variant="body1">
                      <strong>{t('labelling.meta.time')}:</strong> {current.created_at || '-'}
                    </Typography>
                    <Typography variant="body1">
                      <strong>{t('labelling.meta.reason')}:</strong> {current.reason_code}
                    </Typography>
                  </Stack>
                  <Stack direction="row" spacing={1}>
                    <Button
                      size="small"
                      variant={viewMode === 'snapshot' ? 'contained' : 'outlined'}
                      onClick={() => setViewMode('snapshot')}
                    >
                      {t('labelling.view.snapshot')}
                    </Button>
                    <Button
                      size="small"
                      variant={viewMode === 'video' ? 'contained' : 'outlined'}
                      onClick={() => setViewMode('video')}
                    >
                      {t('labelling.view.video')}
                    </Button>
                  </Stack>
                  <LabellingMediaOverlay item={current} viewMode={viewMode} />
                  <Typography variant="body2" color="text.secondary">
                    {t('labelling.predictions.main')}: {current.behavior_label || '-'}
                    {current.behavior_confidence != null
                      ? ` (${(Number(current.behavior_confidence) * 100).toFixed(0)}%)`
                      : ''}
                    {'  '}| {t('labelling.predictions.shadow')}: {current.behavior_shadow_label || '-'}
                    {current.behavior_shadow_confidence != null
                      ? ` (${(Number(current.behavior_shadow_confidence) * 100).toFixed(0)}%)`
                      : ''}
                  </Typography>
                  <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                    <FormControl size="small" sx={{ minWidth: 180 }}>
                      <InputLabel id="behavior-tag-current">{t('labelling.fields.behaviorTag')}</InputLabel>
                      <Select
                        labelId="behavior-tag-current"
                        value={behaviorTag}
                        label={t('labelling.fields.behaviorTag')}
                        onChange={(e) => setBehaviorTag(String(e.target.value))}
                      >
                        <MenuItem value="feeding">feeding</MenuItem>
                        <MenuItem value="perched_idle">perched_idle</MenuItem>
                        <MenuItem value="flying">flying</MenuItem>
                        <MenuItem value="alert">alert</MenuItem>
                      </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 220 }}>
                      <InputLabel id="species-tag-current">{t('labelling.fields.speciesTag')}</InputLabel>
                      <Select
                        labelId="species-tag-current"
                        value={speciesTag}
                        label={t('labelling.fields.speciesTag')}
                        onChange={(e) => setSpeciesTag(String(e.target.value))}
                      >
                        <MenuItem value="">{t('labelling.fields.empty')}</MenuItem>
                        <MenuItem value={current.species_name || ''}>{current.species_name || t('labelling.fields.current')}</MenuItem>
                      </Select>
                    </FormControl>
                  </Stack>
                  <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                    <Tooltip title={t('labelling.shortcuts.confirm')}>
                      <span>
                        <Button size="small" color="success" variant="contained" onClick={doConfirm} disabled={feedback.isPending}>
                          {t('labelling.actions.confirm')}
                        </Button>
                      </span>
                    </Tooltip>
                    <Tooltip title={t('labelling.shortcuts.reject')}>
                      <span>
                        <Button size="small" color="error" variant="outlined" onClick={doReject} disabled={feedback.isPending}>
                          {t('labelling.actions.reject')}
                        </Button>
                      </span>
                    </Tooltip>
                    <Button
                      size="small"
                      color="secondary"
                      variant="outlined"
                      onClick={() =>
                        feedback.mutate({
                          id: current.id,
                          action: 'tag_species',
                          species_tag: speciesTag || current.species_name || '',
                        })
                      }
                      disabled={feedback.isPending}
                    >
                      {t('labelling.actions.tagSpecies')}
                    </Button>
                    <Button size="small" variant="text" onClick={gotoPrev} disabled={currentIndex <= 0}>
                      {t('labelling.actions.prev')}
                    </Button>
                    <Button size="small" variant="text" onClick={gotoNext} disabled={currentIndex >= items.length - 1}>
                      {t('labelling.actions.next')}
                    </Button>
                    <Button
                      size="small"
                      variant="text"
                      onClick={() => patch.mutate({ id: current.id, status: 'pending' })}
                      disabled={patch.isPending}
                    >
                      {t('labelling.actions.skip')}
                    </Button>
                  </Stack>
                </Stack>
              </CardContent>
            </Card>
          ) : null}
          {!q.isLoading && !q.isError && (q.data?.count || 0) === 0 ? (
            <Alert severity="info">{t('labelling.states.empty')}</Alert>
          ) : null}
          {!q.isLoading && !q.isError && items.length === 0 && (q.data?.count || 0) > 0 ? (
            <Alert severity="warning">{t('labelling.states.noFiltered')}</Alert>
          ) : null}
        </Stack>
      </Stack>
      <Dialog
        open={showHelp}
        onClose={() => {
          setShowHelp(false);
          localStorage.setItem('labelling_help_seen', '1');
        }}
      >
        <DialogTitle>{t('labelling.help.title')}</DialogTitle>
        <DialogContent>
          <Typography>{t('labelling.help.step1')}</Typography>
          <Typography>{t('labelling.help.step2')}</Typography>
          <Typography>{t('labelling.help.step3')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              setShowHelp(false);
              localStorage.setItem('labelling_help_seen', '1');
            }}
          >
            {t('labelling.help.gotIt')}
          </Button>
        </DialogActions>
      </Dialog>
    </ProtectedRoute>
  );
};

export default LabellingPage;
