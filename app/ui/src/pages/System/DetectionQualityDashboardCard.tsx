import React from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import Stack from '@mui/material/Stack';
import Grid from '@mui/material/Grid2';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Alert from '@mui/material/Alert';
import Divider from '@mui/material/Divider';
import { LineChart } from '@mui/x-charts/LineChart';
import { useQualityHealthQuery, useQualityTimeseriesQuery } from '../../hooks/useSystemQueries';

function pct(v: number): string {
  return `${(v * 100).toFixed(1)}%`;
}

export const DetectionQualityDashboardCard: React.FC = () => {
  const tsQuery = useQualityTimeseriesQuery('hour');
  const healthQuery = useQualityHealthQuery(24);

  const loading = tsQuery.isLoading || healthQuery.isLoading;
  const err = tsQuery.error || healthQuery.error;
  if (loading) return <LinearProgress />;
  if (err) return <Alert severity="error">Failed to load detection quality dashboard.</Alert>;

  const ts = tsQuery.data?.items ?? [];
  const health = healthQuery.data;
  const x = ts.map((v) => new Date(v.bucket));
  const yoloRatio = ts.map((v) => (v.detections > 0 ? (v.yolo_rows || 0) / v.detections : 0));
  const fallbackRatio = ts.map((v) => v.frigate_ratio || 0);
  const blendedRatio = ts.map((v) =>
    v.detections > 0 ? Math.max(0, 1 - ((v.yolo_rows || 0) + (v.frigate_rows || 0)) / v.detections) : 0,
  );

  const kpis = health?.health_kpis;
  const events = health?.recent_events ?? [];
  return (
    <Card>
      <CardContent>
        <Typography variant="h5" sx={{ mb: 1 }}>
          Detection Quality Dashboard
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          YOLO/Frigate balance, blind score and self-heal trace for the last 24h.
        </Typography>

        <Grid container spacing={1.5} sx={{ mb: 2 }}>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              color={kpis && kpis.blind_score_current > 0.7 ? 'warning' : 'success'}
              label={`blind_score now: ${kpis ? kpis.blind_score_current.toFixed(3) : 'n/a'}`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              color="info"
              label={`fallback ratio 24h: ${kpis ? pct(kpis.fallback_ratio) : 'n/a'}`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              color="default"
              label={`self-heal restart: ${kpis?.self_heal_action_counts.restart ?? 0}`}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6, md: 3 }}>
            <Chip
              color="default"
              label={`infer p95 avg: ${kpis?.inference_latency_p95_ms_avg ?? 'n/a'} ms`}
            />
          </Grid>
        </Grid>

        <Box sx={{ width: '100%', minHeight: 220 }}>
          <LineChart
            xAxis={[
              {
                scaleType: 'time',
                data: x,
              },
            ]}
            yAxis={[{ min: 0, max: 1 }]}
            series={[
              { data: yoloRatio, label: 'YOLO-only ratio', showMark: false },
              { data: blendedRatio, label: 'Blended ratio', showMark: false },
              { data: fallbackRatio, label: 'Frigate fallback ratio', showMark: false },
            ]}
            height={220}
            margin={{ top: 10, bottom: 24, left: 44, right: 12 }}
          />
        </Box>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle1" sx={{ mb: 1 }}>
          Self-heal events
        </Typography>
        <Stack spacing={1}>
          {events.length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              No recent events.
            </Typography>
          ) : (
            events.slice(0, 8).map((ev) => (
              <Box
                key={`${ev.created_at}-${ev.event_type}`}
                sx={{
                  display: 'flex',
                  flexWrap: 'wrap',
                  gap: 1,
                  alignItems: 'center',
                }}
              >
                <Chip size="small" label={ev.event_type} color={ev.severity === 'error' ? 'error' : 'default'} />
                {ev.action ? <Chip size="small" label={ev.action} variant="outlined" /> : null}
                <Typography variant="caption" color="text.secondary">
                  {new Date(ev.created_at).toLocaleString()}
                </Typography>
                {ev.dump_refs?.diagnostics_json ? (
                  <Typography variant="caption" color="text.secondary">
                    dump: {ev.dump_refs.diagnostics_json}
                  </Typography>
                ) : null}
              </Box>
            ))
          )}
        </Stack>
      </CardContent>
    </Card>
  );
};
