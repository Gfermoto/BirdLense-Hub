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
import { AnnotationViewer } from '../../components/AnnotationViewer';
import {
  useExportLabellingCasesMutation,
  useLabellingBatchFeedbackMutation,
  useLabellingCasesQuery,
  useMineLabellingCasesMutation,
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

const BEHAVIORS = ['feeding', 'perched_idle', 'flying', 'alert'];

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  return target.isContentEditable;
}

function reasonHuman(reason: string, t: (k: string) => string) {
  if (reason.includes('blind')) return t('labelling.reasons.blind');
  if (reason.includes('fallback')) return t('labelling.reasons.fallback');
  if (reason.includes('confidence')) return t('labelling.reasons.lowConfidence');
  return reason;
}

function speciesCandidates(item: LabellingCase): string[] {
  const payload = item.payload || {};
  const arr = Array.isArray(payload['species_candidates']) ? payload['species_candidates'] : [];
  const base = arr
    .map((x) => (typeof x === 'string' ? x : typeof x === 'object' && x && 'name' in x ? String((x as { name: string }).name) : ''))
    .filter(Boolean);
  if (item.suggested_species) base.unshift(item.suggested_species);
  if (item.species_name) base.unshift(item.species_name);
  return Array.from(new Set(base)).slice(0, 3);
}

const MediaCanvas: React.FC<{
  item: LabellingCase;
  viewMode: ViewMode;
  selected: boolean;
  onSelect: (v: boolean) => void;
}> = ({ item, viewMode, selected, onSelect }) => {
  const { t } = useTranslation();
  const videoRef = React.useRef<HTMLVideoElement | null>(null);

  React.useEffect(() => {
    const video = videoRef.current;
    if (!video || viewMode !== 'snapshot') return;
    const seek = () => {
      const firstT = item.track_frames?.[0]?.t;
      if (typeof firstT === 'number') video.currentTime = Math.max(0, firstT);
      void video.pause();
    };
    seek();
    video.addEventListener('loadedmetadata', seek, { once: true });
    return () => video.removeEventListener('loadedmetadata', seek);
  }, [item.track_frames, viewMode]);

  const [currentTime, setCurrentTime] = React.useState<number | null>(null);

  if (!item.video_stream_url) return <Alert severity="warning">{t('labelling.media.noMedia')}</Alert>;
  if (!item.bbox && (!item.track_frames || item.track_frames.length === 0)) return <Alert severity="warning">{t('labelling.media.noOverlayData')}</Alert>;

  return (
    <Box sx={{ position: 'relative', width: '100%', aspectRatio: '16 / 9', bgcolor: '#000' }}>
      <Box
        component="video"
        ref={videoRef}
        controls={viewMode === 'video'}
        autoPlay={viewMode === 'video'}
        muted
        preload="metadata"
        sx={{ width: '100%', height: '100%', objectFit: 'contain' }}
        src={item.video_stream_url}
        onTimeUpdate={(e) => setCurrentTime(e.currentTarget.currentTime)}
      />
      <AnnotationViewer
        tracks={[
          {
            id: `case-${item.id}`,
            label: `${item.species_name || t('labelling.labels.speciesUnknown')} (${Math.round((item.confidence || 0) * 100)}%) • ${t('labelling.labels.behavior')}: ${item.behavior_label || item.suggested_behavior || '-'}`,
            color: item.status === 'approved' ? '#22c55e' : item.status === 'rejected' ? '#ef4444' : '#eab308',
            frames: (() => {
              const rows = (item.track_frames || [])
                .filter((x) => Array.isArray(x.bbox) && x.bbox.length === 4)
                .map((x) => ({ t: x.t, bbox: x.bbox }));
              if (rows.length > 0) return rows;
              if (item.bbox && item.bbox.length === 4) return [{ t: null, bbox: item.bbox }];
              return [];
            })(),
          },
        ]}
        currentTime={viewMode === 'video' ? currentTime : item.track_frames?.[0]?.t ?? null}
        selectedTrackId={selected ? `case-${item.id}` : null}
        interactive
        onSelectTrack={(id) => onSelect(Boolean(id))}
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
  const [selectedBox, setSelectedBox] = React.useState(false);
  const q = useLabellingCasesQuery('all', 500);
  const mine = useMineLabellingCasesMutation();
  const batch = useLabellingBatchFeedbackMutation();
  const exp = useExportLabellingCasesMutation();
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
      if (workflowFilter === 'error' && !(item.reason_code.includes('blind') || item.reason_code.includes('fallback'))) return false;
      if (cameraFilter !== 'all' && item.camera_id !== cameraFilter) return false;
      return true;
    });
    return filtered.sort((a, b) => {
      const prA = a.reason_code.includes('blind') ? 0 : a.reason_code.includes('fallback') ? 1 : 2;
      const prB = b.reason_code.includes('blind') ? 0 : b.reason_code.includes('fallback') ? 1 : 2;
      if (prA !== prB) return prA - prB;
      return String(b.created_at || '').localeCompare(String(a.created_at || ''));
    });
  }, [allItems, cameraFilter, status, workflowFilter]);

  React.useEffect(() => {
    if (currentIndex >= items.length) setCurrentIndex(Math.max(0, items.length - 1));
    setSelectedBox(false);
  }, [currentIndex, items.length]);

  const current = items[currentIndex] || null;
  const topSpecies = React.useMemo(() => (current ? speciesCandidates(current) : []), [current]);
  const [speciesTag, setSpeciesTag] = React.useState('');
  const [behaviorTag, setBehaviorTag] = React.useState('feeding');

  React.useEffect(() => {
    if (!current) return;
    setSpeciesTag(current.suggested_species || current.species_name || '');
    setBehaviorTag(current.suggested_behavior || current.behavior_label || 'feeding');
  }, [current?.id, current?.species_name, current?.suggested_behavior, current?.suggested_species, current?.behavior_label]);

  const reviewed = items.filter((x) => x.status !== 'pending').length;
  const progress = items.length > 0 ? (reviewed / items.length) * 100 : 0;
  const gotoNext = () => setCurrentIndex((v) => Math.min(items.length - 1, v + 1));
  const gotoPrev = () => setCurrentIndex((v) => Math.max(0, v - 1));

  const approveAll = React.useCallback(async () => {
    if (!current) return;
    await batch.mutateAsync([
      { kind: 'feedback', case_id: current.id, action: 'tag_species', species_tag: speciesTag || current.species_name || '' },
      { kind: 'feedback', case_id: current.id, action: 'confirm_behavior', behavior_tag: behaviorTag },
      { kind: 'status', case_id: current.id, status: 'approved' },
    ]);
    gotoNext();
  }, [batch, behaviorTag, current, speciesTag]);

  const rejectAll = React.useCallback(async () => {
    if (!current) return;
    await batch.mutateAsync([{ kind: 'feedback', case_id: current.id, action: 'reject_box' }]);
    gotoNext();
  }, [batch, current]);

  const cycleBehavior = React.useCallback(() => {
    setBehaviorTag((prev) => {
      const idx = BEHAVIORS.indexOf(prev);
      return BEHAVIORS[(idx + 1 + BEHAVIORS.length) % BEHAVIORS.length];
    });
  }, []);

  React.useEffect(() => {
    const handler = async (e: KeyboardEvent) => {
      if (isTypingTarget(e.target)) return;
      if (!current) return;
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        await approveAll();
      } else if (e.key === 'Backspace') {
        e.preventDefault();
        await rejectAll();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        gotoNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        gotoPrev();
      } else if (e.key.toLowerCase() === 'b') {
        e.preventDefault();
        cycleBehavior();
      } else if (['1', '2', '3'].includes(e.key)) {
        e.preventDefault();
        const next = topSpecies[Number(e.key) - 1];
        if (next) setSpeciesTag(next);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [approveAll, current, cycleBehavior, rejectAll, topSpecies]);

  return (
    <ProtectedRoute title={t('labelling.title')} requireAdmin={false}>
      <Stack spacing={2}>
        <PageHeader title={t('labelling.title')} description={t('labelling.description')} titleVariant="h4" />
        <Alert severity="info">{t('labelling.hints.trainingPurpose')}</Alert>
        <Card>
          <CardContent>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }}>
              <Button variant="contained" onClick={() => mine.mutate({ lookback_hours: 72, max_rows: 500 })} disabled={mine.isPending}>
                {t('labelling.actions.runMiner')}
              </Button>
              <FormControl size="small" sx={{ minWidth: 120 }}>
                <InputLabel id="lang">{t('labelling.language')}</InputLabel>
                <Select labelId="lang" value={i18n.language.startsWith('ru') ? 'ru' : 'en'} label={t('labelling.language')} onChange={(e) => void i18n.changeLanguage(String(e.target.value))}>
                  <MenuItem value="ru">RU</MenuItem>
                  <MenuItem value="en">EN</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="st">{t('labelling.filters.status')}</InputLabel>
                <Select labelId="st" value={status} label={t('labelling.filters.status')} onChange={(e) => setStatus(e.target.value as FilterStatus)}>
                  <MenuItem value="all">{t('labelling.filters.all')}</MenuItem>
                  <MenuItem value="pending">{t('labelling.status.pending')}</MenuItem>
                  <MenuItem value="approved">{t('labelling.status.approved')}</MenuItem>
                  <MenuItem value="rejected">{t('labelling.status.rejected')}</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 200 }}>
                <InputLabel id="wf">{t('labelling.filters.workflow')}</InputLabel>
                <Select labelId="wf" value={workflowFilter} label={t('labelling.filters.workflow')} onChange={(e) => setWorkflowFilter(e.target.value as WorkflowFilter)}>
                  <MenuItem value="all">{t('labelling.filters.all')}</MenuItem>
                  <MenuItem value="new">{t('labelling.filters.onlyNew')}</MenuItem>
                  <MenuItem value="error">{t('labelling.filters.onlyError')}</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="cam">{t('labelling.filters.camera')}</InputLabel>
                <Select labelId="cam" value={cameraFilter} label={t('labelling.filters.camera')} onChange={(e) => setCameraFilter(String(e.target.value))}>
                  <MenuItem value="all">{t('labelling.filters.all')}</MenuItem>
                  {cameras.map((cam) => (
                    <MenuItem key={cam} value={cam}>
                      {cam}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="export">{t('labelling.export.title')}</InputLabel>
                <Select labelId="export" value={exportFormat} label={t('labelling.export.title')} onChange={(e) => setExportFormat(e.target.value as 'yolo' | 'coco')}>
                  <MenuItem value="yolo">YOLO</MenuItem>
                  <MenuItem value="coco">COCO</MenuItem>
                </Select>
              </FormControl>
              <Button variant="outlined" onClick={() => exp.mutate({ format: exportFormat, status: 'approved' })} disabled={exp.isPending}>
                {t('labelling.export.approved')}
              </Button>
            </Stack>
            <Stack spacing={0.5} sx={{ mt: 1.5 }}>
              <Typography variant="body2">{t('labelling.progressLabel', { done: reviewed, total: items.length })}</Typography>
              <LinearProgress variant="determinate" value={progress} />
            </Stack>
            <Stack direction="row" spacing={1} sx={{ mt: 1 }}>
              <Tooltip title={t('labelling.shortcuts.confirm')}>
                <Chip size="small" label="Enter/Space" />
              </Tooltip>
              <Tooltip title={t('labelling.shortcuts.reject')}>
                <Chip size="small" label="Backspace" />
              </Tooltip>
              <Tooltip title={t('labelling.shortcuts.quickSpecies')}>
                <Chip size="small" label="1/2/3" />
              </Tooltip>
              <Tooltip title={t('labelling.shortcuts.behavior')}>
                <Chip size="small" label="B" />
              </Tooltip>
            </Stack>
          </CardContent>
        </Card>
        {q.isLoading ? <Alert severity="info">{t('labelling.states.loading')}</Alert> : null}
        {q.isError ? <Alert severity="error">{t('labelling.states.error')}</Alert> : null}
        {current ? (
          <Card>
            <CardContent>
              <Stack spacing={1.5}>
                <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                  <Typography variant="h6">{t('labelling.caseTitle', { id: current.id })}</Typography>
                  <Chip size="small" label={current.pre_approved ? t('labelling.status.preApproved') : t(`labelling.status.${current.status}`)} color={statusColor[current.status]} />
                  <Chip size="small" label={reasonHuman(current.reason_code, t)} />
                </Stack>
                <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5}>
                  <Typography variant="body1"><strong>{t('labelling.meta.camera')}:</strong> {current.camera_id || '-'}</Typography>
                  <Typography variant="body1"><strong>{t('labelling.meta.time')}:</strong> {current.created_at || '-'}</Typography>
                  <Typography variant="body1"><strong>{t('labelling.meta.reason')}:</strong> {reasonHuman(current.reason_code, t)}</Typography>
                </Stack>
                <Stack direction="row" spacing={1}>
                  <Button size="small" variant={viewMode === 'snapshot' ? 'contained' : 'outlined'} onClick={() => setViewMode('snapshot')}>
                    {t('labelling.view.snapshot')}
                  </Button>
                  <Button size="small" variant={viewMode === 'video' ? 'contained' : 'outlined'} onClick={() => setViewMode('video')}>
                    {t('labelling.view.video')}
                  </Button>
                </Stack>
                <MediaCanvas item={current} viewMode={viewMode} selected={selectedBox} onSelect={setSelectedBox} />
                <Card variant="outlined">
                  <CardContent>
                    <Typography variant="subtitle2" gutterBottom>
                      {selectedBox ? t('labelling.panels.boxActions') : t('labelling.panels.sessionActions')}
                    </Typography>
                    <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.2}>
                      {selectedBox ? (
                        <>
                          <FormControl size="small" sx={{ minWidth: 220 }}>
                            <InputLabel id="species">{t('labelling.labels.species')}</InputLabel>
                            <Select labelId="species" value={speciesTag} label={t('labelling.labels.species')} onChange={(e) => setSpeciesTag(String(e.target.value))}>
                              {(topSpecies.length > 0 ? topSpecies : [current.species_name || 'unknown']).map((s) => (
                                <MenuItem key={s} value={s}>
                                  {s}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                          <FormControl size="small" sx={{ minWidth: 220 }}>
                            <InputLabel id="behavior">{t('labelling.labels.behavior')}</InputLabel>
                            <Select labelId="behavior" value={behaviorTag} label={t('labelling.labels.behavior')} onChange={(e) => setBehaviorTag(String(e.target.value))}>
                              {BEHAVIORS.map((b) => (
                                <MenuItem key={b} value={b}>
                                  {b}
                                </MenuItem>
                              ))}
                            </Select>
                          </FormControl>
                          <Button variant="contained" color="success" onClick={() => void approveAll()} disabled={batch.isPending}>
                            {t('labelling.actions.approveAll')}
                          </Button>
                          <Button variant="outlined" color="error" onClick={() => void rejectAll()} disabled={batch.isPending}>
                            {t('labelling.actions.reject')}
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button variant="contained" color="success" onClick={() => void approveAll()} disabled={batch.isPending}>
                            {t('labelling.actions.approveAndNext')}
                          </Button>
                          <Button variant="outlined" color="error" onClick={() => void rejectAll()} disabled={batch.isPending}>
                            {t('labelling.actions.rejectAndNext')}
                          </Button>
                        </>
                      )}
                      <Button size="small" variant="text" onClick={gotoPrev} disabled={currentIndex <= 0}>
                        {t('labelling.actions.prev')}
                      </Button>
                      <Button size="small" variant="text" onClick={gotoNext} disabled={currentIndex >= items.length - 1}>
                        {t('labelling.actions.next')}
                      </Button>
                    </Stack>
                  </CardContent>
                </Card>
              </Stack>
            </CardContent>
          </Card>
        ) : null}
        {!q.isLoading && !q.isError && (q.data?.count || 0) === 0 ? <Alert severity="info">{t('labelling.states.empty')}</Alert> : null}
        {!q.isLoading && !q.isError && items.length === 0 && (q.data?.count || 0) > 0 ? <Alert severity="warning">{t('labelling.states.noFiltered')}</Alert> : null}
      </Stack>
      <Dialog open={showHelp} onClose={() => setShowHelp(false)}>
        <DialogTitle>{t('labelling.help.title')}</DialogTitle>
        <DialogContent>
          <Typography>{t('labelling.help.step1')}</Typography>
          <Typography>{t('labelling.help.step2')}</Typography>
          <Typography>{t('labelling.help.step3')}</Typography>
        </DialogContent>
        <DialogActions>
          <Button
            onClick={() => {
              localStorage.setItem('labelling_help_seen', '1');
              setShowHelp(false);
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
