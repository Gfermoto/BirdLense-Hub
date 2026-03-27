import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
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
import VideocamIcon from '@mui/icons-material/Videocam';
import CloudIcon from '@mui/icons-material/Cloud';
import DeveloperBoardIcon from '@mui/icons-material/DeveloperBoard';
import GroupsIcon from '@mui/icons-material/Groups';
import { BASE_API_URL } from '../../api/api';

interface MetricCardProps {
  icon: React.ElementType;
  title: string;
  value: string;
  percent: number;
}

const CARD_MIN_HEIGHT = 130;

const MetricCard: React.FC<MetricCardProps> = ({
  icon: Icon,
  title,
  value,
  percent,
}) => (
  <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
        <Icon color="action" />
        <Typography variant="h6">{title}</Typography>
      </Box>
      <LinearProgress
        variant="determinate"
        value={percent}
        sx={{ mb: 2, height: 8, borderRadius: 1 }}
      />
      <Typography variant="body2" color="text.secondary">
        {value}
      </Typography>
    </CardContent>
  </Card>
);

export const SystemMonitor = () => {
  const { t } = useTranslation();
  const [visitorsDays, setVisitorsDays] = useState<number>(7);
  const { data, error, isLoading } = useQuery({
    queryKey: ['systemMetrics', visitorsDays],
    queryFn: async () => {
      const response = await fetch(
        `${BASE_API_URL}/system/metrics?visitors_days=${visitorsDays}`,
      );
      if (!response.ok) throw new Error('Failed to fetch system metrics');
      return response.json();
    },
    refetchInterval: 5000,
  });

  if (isLoading) return <LinearProgress />;
  if (error)
    return <Typography color="error">{t('system.errorLoadMetrics')}</Typography>;

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('system.resources')}
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

      <Grid container spacing={3}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
            <CardContent>
              <Box
                sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}
              >
                <SpeedIcon color="action" />
                <Typography variant="h6">{t('system.cpu')}</Typography>
              </Box>
              <LinearProgress
                variant="determinate"
                value={data.cpu.percent}
                sx={{ mb: 2, height: 8, borderRadius: 1 }}
              />
              <Typography variant="body2" color="text.secondary">
                {t('system.usagePercent', { percent: data.cpu.percent })}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <MetricCard
            icon={MemoryIcon}
            title={t('system.memory')}
            value={`${data.memory.used}GB / ${data.memory.total}GB (${data.memory.percent}%)`}
            percent={data.memory.percent}
          />
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <GroupsIcon color="action" />
                <Typography variant="h6">{t('system.uniqueVisitors')}</Typography>
              </Box>
              <Typography variant="h4" sx={{ lineHeight: 1.2 }}>
                {data.visitors?.unique_visits ?? 0}
              </Typography>
              <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                {t('system.uniqueVisitorsHint', {
                  days: data.visitors?.period_days ?? visitorsDays,
                  activeDays: data.visitors?.active_days ?? 0,
                })}
              </Typography>
            </CardContent>
          </Card>
        </Grid>

        <Grid size={{ xs: 12, md: 4 }}>
          <MetricCard
            icon={StorageIcon}
            title={t('system.disk')}
            value={`${data.disk.used}GB / ${data.disk.total}GB (${data.disk.percent}%)`}
            percent={data.disk.percent}
          />
        </Grid>

        {data.encoding != null && (
          <Grid size={{ xs: 12, md: 4 }}>
            <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <VideocamIcon color="action" />
                  <Typography variant="h6">{t('system.encoding')}</Typography>
                </Box>
                <Typography variant="body2" color="text.secondary">
                  {t('system.encodingUsed')}:{' '}
                  {data.encoding_used === 'vaapi'
                    ? t('system.encodingVaapi')
                    : data.encoding_used === 'cpu'
                      ? t('system.encodingCpu')
                      : data.encoding === 'intel'
                        ? t('system.encodingVaapi')
                        : t('system.encodingCpu')}
                </Typography>
                {data.encoding === 'intel' && data.encoding_used === 'cpu' && (
                  <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 1 }}>
                    {t('system.encodingGpuUnavailable')}
                  </Typography>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}

        {data.processor_mqtt != null && (
          <Grid size={{ xs: 12, md: 4 }}>
            <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <CloudIcon color="action" />
                  <Typography variant="h6">{t('system.processorMqtt')}</Typography>
                </Box>
                <Typography variant="body2" color={data.processor_mqtt === 'ok' ? 'text.secondary' : 'error.main'}>
                  {data.processor_mqtt === 'ok' ? t('status.mqttOk') : data.processor_mqtt === 'error' ? t('status.mqttError') : t('status.mqttUnknown')}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        )}

        {(data.encoding === 'intel' || data.gpu_percent != null) && (
          <Grid size={{ xs: 12, md: 4 }}>
            <Card sx={{ minHeight: CARD_MIN_HEIGHT }}>
              <CardContent>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                  <DeveloperBoardIcon color="action" />
                  <Typography variant="h6">{t('system.gpu')}</Typography>
                </Box>
                {data.gpu_percent != null ? (
                  <>
                    <LinearProgress
                      variant="determinate"
                      value={data.gpu_percent}
                      sx={{ mb: 2, height: 8, borderRadius: 1 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      {t('system.usagePercent', { percent: data.gpu_percent })}
                    </Typography>
                  </>
                ) : (
                  <>
                    <LinearProgress
                      variant="determinate"
                      value={0}
                      sx={{ mb: 2, height: 8, borderRadius: 1, opacity: 0.4 }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      {t('system.gpuNoData')}
                    </Typography>
                  </>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
};
