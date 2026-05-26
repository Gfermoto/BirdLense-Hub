import React from 'react';
import { useTranslation } from 'react-i18next';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Grid from '@mui/material/Grid2';
import Chip from '@mui/material/Chip';
import Alert from '@mui/material/Alert';
import LinearProgress from '@mui/material/LinearProgress';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import { useTriggerGraphQuery } from '../../hooks/useSystemQueries';

const SOURCES = ['frigate', 'opencv', 'yolo', 'birdnet', 'scale'] as const;

export const TriggerGraphDashboardCard: React.FC = () => {
  const { t } = useTranslation();
  const query = useTriggerGraphQuery(24);

  if (query.isLoading) return <LinearProgress />;
  if (query.error) {
    return <Alert severity="error">{t('system.triggerGraph.loadError')}</Alert>;
  }

  const data = query.data;
  const metrics = data?.metrics_by_source ?? {};
  const recent = data?.recent_sessions ?? [];

  return (
    <Card>
      <CardContent>
        <Typography variant="h5" sx={{ mb: 1 }}>
          {t('system.triggerGraph.title')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.triggerGraph.description')}
        </Typography>

        {data?.session_count === 0 ? (
          <Alert severity="info">{t('system.triggerGraph.noData')}</Alert>
        ) : null}

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {t('system.triggerGraph.bySource')} ({data?.session_count ?? 0}{' '}
          {t('system.triggerGraph.sessions')})
        </Typography>
        <Grid container spacing={1} sx={{ mb: 2 }}>
          {SOURCES.map((src) => {
            const m = metrics[src] ?? {};
            return (
              <Grid key={src} size={{ xs: 12, sm: 6, md: 4 }}>
                <Stack spacing={0.5} sx={{ p: 1, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                  <Chip size="small" label={src.toUpperCase()} color="primary" variant="outlined" />
                  <Typography variant="caption" display="block">
                    {t('system.triggerGraph.init')}: {m.recordings_initiated ?? 0} ·{' '}
                    {t('system.triggerGraph.species')}: {m.species_persisted ?? 0}
                  </Typography>
                  <Typography variant="caption" display="block" color="error.main">
                    FP: {t('system.triggerGraph.fpEmpty')}{' '}
                    {m.fp_empty_recording ?? 0} / {t('system.triggerGraph.fpReject')}{' '}
                    {m.fp_rejected_noise ?? 0}
                  </Typography>
                  <Typography variant="caption" display="block" color="warning.main">
                    FN: {t('system.triggerGraph.fnSilent')} {m.fn_detector_silent ?? 0} ·{' '}
                    {t('system.triggerGraph.fnNoSpecies')} {m.fn_no_persisted_species ?? 0}
                  </Typography>
                </Stack>
              </Grid>
            );
          })}
        </Grid>

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {t('system.triggerGraph.recentSessions')}
        </Typography>
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{t('system.triggerGraph.colTime')}</TableCell>
              <TableCell>{t('system.triggerGraph.colCamera')}</TableCell>
              <TableCell>{t('system.triggerGraph.colInit')}</TableCell>
              <TableCell align="right">{t('system.triggerGraph.colSpecies')}</TableCell>
              <TableCell align="right">FP</TableCell>
              <TableCell align="right">FN</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {recent.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6}>
                  <Typography variant="body2" color="text.secondary">
                    —
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              recent.map((row) => (
                <TableRow key={`${row.created_at}-${row.camera_id}`}>
                  <TableCell>
                    {row.created_at
                      ? new Date(String(row.created_at)).toLocaleString()
                      : '—'}
                  </TableCell>
                  <TableCell>{row.camera_id ?? '—'}</TableCell>
                  <TableCell>{row.init_source ?? '—'}</TableCell>
                  <TableCell align="right">{row.species_persisted ?? 0}</TableCell>
                  <TableCell align="right">{row.fp_empty_recording ?? 0}</TableCell>
                  <TableCell align="right">{row.fn_detector_silent ?? 0}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
