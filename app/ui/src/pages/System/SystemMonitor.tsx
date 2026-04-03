import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { formatLocalTime } from '../../util';
import { useState, useEffect, useMemo } from 'react';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import LinearProgress from '@mui/material/LinearProgress';
import Grid from '@mui/material/Grid2';
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import MemoryIcon from '@mui/icons-material/Memory';
import StorageIcon from '@mui/icons-material/Storage';
import SpeedIcon from '@mui/icons-material/Speed';
import DeveloperBoardIcon from '@mui/icons-material/DeveloperBoard';
import GroupsIcon from '@mui/icons-material/Groups';
import { LineChart } from '@mui/x-charts/LineChart';
import { BASE_API_URL } from '../../api/api';

const LIVE_TAIL_MAX = 48;
const CARD_MIN_HEIGHT = 280;

type ChartPoint = {
  at: Date;
  cpu: number;
  memory: number;
  disk: number;
  gpu: number | null;
};

interface LiveMetrics {
  cpu: { percent: number };
  memory: { total: number; used: number; percent: number };
  disk: { total: number; used: number; percent: number };
  encoding: string;
  gpu_percent: number | null;
}

interface VisitorStats {
  period_days: number;
  unique_visits: number;
  browser_count?: number;
  active_days: number;
  device_breakdown?: Record<string, number>;
  method: string;
}

interface HistorySample {
  t: string;
  cpu: number;
  memory: number;
  disk: number;
  gpu: number | null;
}

interface MetricsHistoryResponse {
  samples: HistorySample[];
  sample_interval_seconds?: number;
  retention_hours?: number;
  hours_requested?: number;
}

type MetricKey = 'cpu' | 'memory' | 'disk' | 'gpu';

function SparkMetricCard({
  title,
  icon: Icon,
  chartPoints,
  metricKey,
  collectingLabel,
  currentText,
  yMax = 100,
}: {
  title: string;
  icon: React.ElementType;
  chartPoints: ChartPoint[];
  metricKey: MetricKey;
  collectingLabel: string;
  currentText: string;
  yMax?: number;
}) {
  const times = useMemo(
    () => chartPoints.map((p) => p.at),
    [chartPoints],
  );
  const seriesData = useMemo(
    () =>
      chartPoints.map((p) => {
        const v = p[metricKey];
        return v == null ? null : v;
      }),
    [chartPoints, metricKey],
  );
  const hasChart = chartPoints.length >= 2;

  return (
    <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
      <CardContent>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
          <Icon color="action" />
          <Typography variant="h6">{title}</Typography>
        </Box>
        <Box sx={{ width: '100%', height: 176, mb: 1 }}>
          {hasChart ? (
            <LineChart
              hideLegend
              skipAnimation
              xAxis={[
                {
                  data: times,
                  scaleType: 'time',
                  valueFormatter: (d: Date) =>
                    formatLocalTime(d),
                  tickLabelStyle: { fontSize: 10 },
                },
              ]}
              yAxis={[{ min: 0, max: yMax }]}
              series={[
                {
                  data: seriesData,
                  showMark: false,
                  connectNulls: false,
                },
              ]}
              height={176}
              margin={{ top: 8, bottom: 24, left: 44, right: 12 }}
            />
          ) : (
            <Box
              sx={{
                height: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Typography variant="body2" color="text.secondary" textAlign="center">
                {collectingLabel}
              </Typography>
            </Box>
          )}
        </Box>
        <Typography variant="body2" color="text.secondary">
          {currentText}
        </Typography>
      </CardContent>
    </Card>
  );
}

export const SystemMonitor = () => {
  const { t } = useTranslation();
  const [visitorsDays, setVisitorsDays] = useState<number>(7);
  const [historyHours, setHistoryHours] = useState<number>(24);
  const [liveTail, setLiveTail] = useState<ChartPoint[]>([]);

  const liveQuery = useQuery({
    queryKey: ['systemMetricsLive'],
    queryFn: async (): Promise<LiveMetrics> => {
      const response = await fetch(`${BASE_API_URL}/system/metrics`);
      if (!response.ok) throw new Error('Failed to fetch system metrics');
      return response.json();
    },
    refetchInterval: 5000,
  });

  const historyQuery = useQuery({
    queryKey: ['systemMetricsHistory', historyHours],
    queryFn: async (): Promise<MetricsHistoryResponse> => {
      const response = await fetch(
        `${BASE_API_URL}/system/metrics/history?hours=${historyHours}&max_points=500`,
      );
      if (!response.ok) throw new Error('Failed to fetch metrics history');
      return response.json();
    },
    staleTime: 60_000,
  });

  const visitorsQuery = useQuery({
    queryKey: ['systemVisitors', visitorsDays],
    queryFn: async (): Promise<VisitorStats> => {
      const response = await fetch(
        `${BASE_API_URL}/system/visitors?days=${visitorsDays}`,
      );
      if (!response.ok) throw new Error('Failed to fetch visitor stats');
      return response.json();
    },
    staleTime: 60_000,
  });

  useEffect(() => {
    setLiveTail([]);
  }, [historyHours]);

  useEffect(() => {
    const live = liveQuery.data;
    if (!live) return;
    setLiveTail((prev) => {
      const next: ChartPoint[] = [
        ...prev,
        {
          at: new Date(),
          cpu: live.cpu.percent,
          memory: live.memory.percent,
          disk: live.disk.percent,
          gpu: live.gpu_percent,
        },
      ];
      return next.length > LIVE_TAIL_MAX
        ? next.slice(-LIVE_TAIL_MAX)
        : next;
    });
  }, [liveQuery.dataUpdatedAt, liveQuery.data]);

  const chartPoints = useMemo((): ChartPoint[] => {
    const server: ChartPoint[] = (historyQuery.data?.samples ?? []).map(
      (s) => ({
        at: new Date(s.t),
        cpu: s.cpu,
        memory: s.memory,
        disk: s.disk,
        gpu: s.gpu,
      }),
    );
    if (server.length === 0) return [...liveTail];
    const lastServerMs = server[server.length - 1]!.at.getTime();
    const tail = liveTail.filter((p) => p.at.getTime() > lastServerMs - 1000);
    return [...server, ...tail];
  }, [historyQuery.data?.samples, liveTail]);

  const live = liveQuery.data;

  if (liveQuery.isLoading) return <LinearProgress />;
  if (liveQuery.error)
    return (
      <Typography color="error">{t('system.errorLoadMetrics')}</Typography>
    );

  if (!live) return null;

  const showGpuCard =
    live.encoding === 'intel' || live.gpu_percent != null;

  const visitors = visitorsQuery.data;

  const historySubtitle =
    historyQuery.data?.retention_hours != null &&
    historyQuery.data?.sample_interval_seconds != null
      ? t('system.serverHistoryMeta', {
          hours: historyHours,
          retention: historyQuery.data.retention_hours,
          interval: historyQuery.data.sample_interval_seconds,
        })
      : null;

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h5" sx={{ mb: 1 }}>
        {t('system.resources')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('system.liveTrendHint')}
      </Typography>
      {historySubtitle ? (
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {historySubtitle}
        </Typography>
      ) : (
        <Box sx={{ mb: 2 }} />
      )}

      <Box
        sx={{
          mb: 2,
          display: 'flex',
          justifyContent: 'flex-end',
          flexWrap: 'wrap',
          gap: 2,
        }}
      >
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="metrics-history-hours-label">
            {t('system.metricsHistoryWindow')}
          </InputLabel>
          <Select
            labelId="metrics-history-hours-label"
            value={historyHours}
            label={t('system.metricsHistoryWindow')}
            onChange={(e) => setHistoryHours(Number(e.target.value))}
          >
            <MenuItem value={6}>{t('system.history6h')}</MenuItem>
            <MenuItem value={24}>{t('system.history24h')}</MenuItem>
            <MenuItem value={48}>{t('system.history48h')}</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {historyQuery.isError ? (
        <Typography color="error" sx={{ mb: 2 }}>
          {t('system.errorLoadHistory')}
        </Typography>
      ) : null}

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 4 }}>
          <SparkMetricCard
            icon={SpeedIcon}
            title={t('system.cpu')}
            chartPoints={chartPoints}
            metricKey="cpu"
            collectingLabel={t('system.chartCollecting')}
            currentText={t('system.usagePercent', { percent: live.cpu.percent })}
            yMax={100}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SparkMetricCard
            icon={MemoryIcon}
            title={t('system.memory')}
            chartPoints={chartPoints}
            metricKey="memory"
            collectingLabel={t('system.chartCollecting')}
            currentText={`${live.memory.used}GB / ${live.memory.total}GB (${live.memory.percent}%)`}
            yMax={100}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SparkMetricCard
            icon={StorageIcon}
            title={t('system.disk')}
            chartPoints={chartPoints}
            metricKey="disk"
            collectingLabel={t('system.chartCollecting')}
            currentText={`${live.disk.used}GB / ${live.disk.total}GB (${live.disk.percent}%)`}
            yMax={100}
          />
        </Grid>

        {showGpuCard ? (
          <Grid size={{ xs: 12, md: 4 }}>
            <SparkMetricCard
              icon={DeveloperBoardIcon}
              title={t('system.gpu')}
              chartPoints={chartPoints}
              metricKey="gpu"
              collectingLabel={t('system.chartCollecting')}
              currentText={
                live.gpu_percent != null
                  ? t('system.usagePercent', { percent: live.gpu_percent })
                  : t('system.gpuNoData')
              }
              yMax={100}
            />
          </Grid>
        ) : null}
      </Grid>

      <Typography variant="h5" sx={{ mt: 4, mb: 2 }}>
        {t('system.uniqueVisitorsSection')}
      </Typography>
      <Box sx={{ mb: 2, display: 'flex', justifyContent: 'flex-end' }}>
        <FormControl size="small" sx={{ minWidth: 220 }}>
          <InputLabel id="visitors-period-label">
            {t('system.uniqueVisitorsPeriod')}
          </InputLabel>
          <Select
            labelId="visitors-period-label"
            value={visitorsDays}
            label={t('system.uniqueVisitorsPeriod')}
            onChange={(e) => setVisitorsDays(Number(e.target.value))}
          >
            <MenuItem value={1}>{t('system.lastDays', { count: 1 })}</MenuItem>
            <MenuItem value={7}>{t('system.lastDays', { count: 7 })}</MenuItem>
            <MenuItem value={30}>{t('system.lastDays', { count: 30 })}</MenuItem>
          </Select>
        </FormControl>
      </Box>

      {visitorsQuery.isLoading ? (
        <LinearProgress />
      ) : visitorsQuery.error ? (
        <Typography color="error">{t('system.errorLoadVisitors')}</Typography>
      ) : visitors ? (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card sx={{ minHeight: 140 }}>
              <CardContent>
                <Box
                  sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}
                >
                  <GroupsIcon color="action" />
                  <Typography variant="h6">
                    {t('system.uniqueVisitors')}
                  </Typography>
                </Box>
                <Typography variant="h4" sx={{ lineHeight: 1.2 }}>
                  {visitors.browser_count ?? visitors.unique_visits}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  {t('system.uniqueVisitorsHint', {
                    days: visitors.period_days ?? visitorsDays,
                    activeDays: visitors.active_days ?? 0,
                  })}
                </Typography>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mt: 1 }}
                >
                  {t('system.visitorDeviceBreakdown', {
                    desktop: visitors.device_breakdown?.desktop ?? 0,
                    mobile: visitors.device_breakdown?.mobile ?? 0,
                    tablet: visitors.device_breakdown?.tablet ?? 0,
                  })}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : null}
    </Box>
  );
};
