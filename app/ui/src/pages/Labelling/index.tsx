import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import { BASE_API_URL } from '../../api/client';
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
import type { LabellingCaseStatus } from '../../api/labelling';

type FilterStatus = LabellingCaseStatus | 'all';

const statusColor: Record<LabellingCaseStatus, 'default' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
};

export const LabellingPage: React.FC = () => {
  useDocumentTitle('Labelling');
  const [status, setStatus] = React.useState<FilterStatus>('all');
  const [exportFormat, setExportFormat] = React.useState<'yolo' | 'coco'>('yolo');
  const q = useLabellingCasesQuery(status, 150);
  const mine = useMineLabellingCasesMutation();
  const patch = usePatchLabellingCaseMutation();
  const feedback = useLabellingFeedbackMutation();
  const exp = useExportLabellingCasesMutation();
  const [behaviorTag, setBehaviorTag] = React.useState('feeding');
  const [speciesTag, setSpeciesTag] = React.useState('');

  return (
    <ProtectedRoute title="Labelling" requireAdmin={false}>
      <Stack spacing={2}>
        <PageHeader
          title="Active Learning / Labelling"
          description="Hard cases queue: blind-score, fallback ratio, borderline confidence."
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
                Run Hard-Case Miner
              </Button>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="labelling-status-label">Status</InputLabel>
                <Select
                  labelId="labelling-status-label"
                  value={status}
                  label="Status"
                  onChange={(e) => setStatus(e.target.value as FilterStatus)}
                >
                  <MenuItem value="all">all</MenuItem>
                  <MenuItem value="pending">pending</MenuItem>
                  <MenuItem value="approved">approved</MenuItem>
                  <MenuItem value="rejected">rejected</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="labelling-export-label">Export</InputLabel>
                <Select
                  labelId="labelling-export-label"
                  value={exportFormat}
                  label="Export"
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
                Export approved
              </Button>
            </Stack>
            {mine.data ? (
              <Alert sx={{ mt: 1.5 }} severity="info">
                Miner: created {mine.data.created}, skipped {mine.data.skipped}
              </Alert>
            ) : null}
            {exp.data ? (
              <Alert sx={{ mt: 1.5 }} severity="success">
                Export done: {exp.data.format} {exp.data.version} ({exp.data.path})
              </Alert>
            ) : null}
          </CardContent>
        </Card>
        <Stack spacing={1.5}>
          {q.isLoading ? <Alert severity="info">Загрузка...</Alert> : null}
          {q.isError ? (
            <Alert severity="error">
              Ошибка загрузки очереди. Проверьте авторизацию и доступность API `/api/ui/labelling/cases`.
            </Alert>
          ) : null}
          {(q.data?.items || []).map((item) => (
            <Card key={item.id}>
              <CardContent>
                <Stack spacing={1}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="subtitle1">Case #{item.id}</Typography>
                    <Chip size="small" label={item.status} color={statusColor[item.status]} />
                    <Chip size="small" label={item.reason_code} />
                    {item.species_name ? <Chip size="small" label={item.species_name} variant="outlined" /> : null}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    conf={item.confidence ?? '-'} blind_score={item.blind_score ?? '-'} fallback_ratio=
                    {item.fallback_ratio ?? '-'} camera={item.camera_id ?? '-'}
                  </Typography>
                  {item.video_id ? (
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Tracklet preview (video #{item.video_id})
                      </Typography>
                      <Box
                        component="video"
                        controls
                        muted
                        preload="metadata"
                        sx={{ width: '100%', maxHeight: 220, borderRadius: 1, mt: 0.5 }}
                        src={item.video_stream_url || `${BASE_API_URL}/videos/${item.video_id}/stream`}
                      />
                    </Box>
                  ) : (
                    <Alert severity="warning">
                      Нет медиа для этого кейса. Используйте сидирование (`python3 scripts/seed_labelling_queue.py`) или
                      откройте кейс из последних детекций с `video_id`.
                    </Alert>
                  )}
                  <Typography variant="body2" color="text.secondary">
                    Main: {item.behavior_label || '-'}
                    {item.behavior_confidence != null
                      ? ` (${(Number(item.behavior_confidence) * 100).toFixed(0)}%)`
                      : ''}
                    {'  '}| Shadow: {item.behavior_shadow_label || '-'}
                    {item.behavior_shadow_confidence != null
                      ? ` (${(Number(item.behavior_shadow_confidence) * 100).toFixed(0)}%)`
                      : ''}
                  </Typography>
                  <Stack direction={{ xs: 'column', md: 'row' }} spacing={1}>
                    <FormControl size="small" sx={{ minWidth: 180 }}>
                      <InputLabel id={`behavior-tag-${item.id}`}>Behavior Tag</InputLabel>
                      <Select
                        labelId={`behavior-tag-${item.id}`}
                        value={behaviorTag}
                        label="Behavior Tag"
                        onChange={(e) => setBehaviorTag(String(e.target.value))}
                      >
                        <MenuItem value="feeding">feeding</MenuItem>
                        <MenuItem value="perched_idle">perched_idle</MenuItem>
                        <MenuItem value="flying">flying</MenuItem>
                        <MenuItem value="alert">alert</MenuItem>
                      </Select>
                    </FormControl>
                    <FormControl size="small" sx={{ minWidth: 220 }}>
                      <InputLabel id={`species-tag-${item.id}`}>Tag Species</InputLabel>
                      <Select
                        labelId={`species-tag-${item.id}`}
                        value={speciesTag}
                        label="Tag Species"
                        onChange={(e) => setSpeciesTag(String(e.target.value))}
                      >
                        <MenuItem value="">(empty)</MenuItem>
                        <MenuItem value={item.species_name || ''}>{item.species_name || '(current)'}</MenuItem>
                      </Select>
                    </FormControl>
                  </Stack>
                  <Box>
                    <Button
                      size="small"
                      onClick={() => patch.mutate({ id: item.id, status: 'approved' })}
                      disabled={patch.isPending}
                    >
                      Approve
                    </Button>
                    <Button
                      size="small"
                      onClick={() => patch.mutate({ id: item.id, status: 'rejected' })}
                      disabled={patch.isPending}
                    >
                      Reject
                    </Button>
                    <Button
                      size="small"
                      onClick={() => patch.mutate({ id: item.id, status: 'pending' })}
                      disabled={patch.isPending}
                    >
                      Reset
                    </Button>
                    <Button
                      size="small"
                      color="success"
                      onClick={() =>
                        feedback.mutate({
                          id: item.id,
                          action: 'confirm_behavior',
                          behavior_tag: behaviorTag,
                        })
                      }
                      disabled={feedback.isPending}
                    >
                      Confirm Behavior
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      onClick={() => feedback.mutate({ id: item.id, action: 'reject_box' })}
                      disabled={feedback.isPending}
                    >
                      Reject Box
                    </Button>
                    <Button
                      size="small"
                      color="secondary"
                      onClick={() =>
                        feedback.mutate({
                          id: item.id,
                          action: 'tag_species',
                          species_tag: speciesTag || item.species_name || '',
                        })
                      }
                      disabled={feedback.isPending}
                    >
                      Tag Species
                    </Button>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          ))}
          {!q.isLoading && !q.isError && (q.data?.count || 0) === 0 ? (
            <Alert severity="info">Нет данных. Запусти Hard-Case Miner или seed: `python3 scripts/seed_labelling_queue.py`.</Alert>
          ) : null}
        </Stack>
      </Stack>
    </ProtectedRoute>
  );
};

export default LabellingPage;
