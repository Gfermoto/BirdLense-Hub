import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
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

const HISTORY_MAX = 72;
const CARD_MIN_HEIGHT = 280;

type HistoryPoint = {
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
  active_days: number;
  method: string;
}

function SparkMetricCard({
  title,
  icon: Icon,
  seriesData,
  collectingLabel,
  currentText,
  yMax = 100,
}: {
  title: string;
  icon: React.ElementType;
  seriesData: (number | null)[];
  collectingLabel: string;
  currentText: string;
  yMax?: number;
}) {
  const xData = useMemo(
    () => Array.from({ length: seriesData.length }, (_, i) => i),
    [seriesData.length],
  );
  const hasChart = seriesData.length >= 2;

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
                  data: xData,
                  scaleType: 'linear',
                  tickLabelStyle: { fontSize: 0 },
                  tickSize: 0,
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
              margin={{ top: 8, bottom: 16, left: 44, right: 12 }}
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
  const [history, setHistory] = useState<HistoryPoint[]>([]);

  const liveQuery = useQuery({
    queryKey: ['systemMetricsLive'],
    queryFn: async (): Promise<LiveMetrics> => {
      const response = await fetch(`${BASE_API_URL}/system/metrics`);
      if (!response.ok) throw new Error('Failed to fetch system metrics');
      return response.json();
    },
    refetchInterval: 5000,
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
    const live = liveQuery.data;
    if (!live) return;
    setHistory((prev) => {
      const next: HistoryPoint[] = [
        ...prev,
        {
          cpu: live.cpu.percent,
          memory: live.memory.percent,
          disk: live.disk.percent,
          gpu: live.gpu_percent,
        },
      ];
      return next.length > HISTORY_MAX ? next.slice(-HISTORY_MAX) : next;
    });
  }, [liveQuery.dataUpdatedAt, liveQuery.data]);

  const live = liveQuery.data;

  const cpuSeries = useMemo(
    () => history.map((h) => h.cpu),
    [history],
  );
  const memSeries = useMemo(
    () => history.map((h) => h.memory),
    [history],
  );
  const diskSeries = useMemo(
    () => history.map((h) => h.disk),
    [history],
  );
  const gpuSeries = useMemo(
    () => history.map((h) => (h.gpu == null ? null : h.gpu)),
    [history],
  );

  if (liveQuery.isLoading) return <LinearProgress />;
  if (liveQuery.error)
    return (
      <Typography color="error">{t('system.errorLoadMetrics')}</Typography>
    );

  if (!live) return null;

  const showGpuCard =
    live.encoding === 'intel' || live.gpu_percent != null;

  const visitors = visitorsQuery.data;

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h5" sx={{ mb: 1 }}>
        {t('system.resources')}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        {t('system.liveTrendHint')}
      </Typography>

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 4 }}>
          <SparkMetricCard
            icon={SpeedIcon}
            title={t('system.cpu')}
            seriesData={cpuSeries}
            collectingLabel={t('system.chartCollecting')}
            currentText={t('system.usagePercent', { percent: live.cpu.percent })}
            yMax={100}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SparkMetricCard
            icon={MemoryIcon}
            title={t('system.memory')}
            seriesData={memSeries}
            collectingLabel={t('system.chartCollecting')}
            currentText={`${live.memory.used}GB / ${live.memory.total}GB (${live.memory.percent}%)`}
            yMax={100}
          />
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <SparkMetricCard
            icon={StorageIcon}
            title={t('system.disk')}
            seriesData={diskSeries}
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
              seriesData={gpuSeries}
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
                  {visitors.unique_visits}
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
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      ) : null}
    </Box>
  );
};
