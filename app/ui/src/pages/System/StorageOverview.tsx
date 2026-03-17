import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import axios from 'axios';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import { BarChart } from '@mui/x-charts/BarChart';
import dayjs from 'dayjs';
import { BASE_API_URL } from '../../api/api';

interface StorageStats {
  date: string;
  fileCount: number;
  totalSize: number;
}

interface ChartDataPoint {
  [key: string]: string | number;
  date: string;
  size: number;
}

const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.min(
    Math.floor(Math.log(bytes) / Math.log(k)),
    sizes.length - 1,
  );
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${sizes[i]}`;
};

export const StorageOverview = () => {
  const { t } = useTranslation();
  const { data: storageStats, isLoading } = useQuery<StorageStats[]>({
    queryKey: ['storageStats'],
    queryFn: async () => {
      const { data } = await axios.get<StorageStats[]>(
        `${BASE_API_URL}/storage/stats`,
      );
      return data;
    },
  });

  if (isLoading) {
    return <Typography>{t('storage.loadingStats')}</Typography>;
  }

  const chartData: ChartDataPoint[] =
    storageStats?.map((stat) => ({
      date: dayjs(stat.date).format('MM/DD'),
      size: Number((stat.totalSize / (1024 * 1024)).toFixed(2)),
    })) || [];
  const totalSize =
    storageStats?.reduce((acc, stat) => acc + stat.totalSize, 0) || 0;
  const totalFiles =
    storageStats?.reduce((acc, stat) => acc + stat.fileCount, 0) || 0;

  return (
    <Box>
      <Typography variant="h5" sx={{ mb: 3 }}>
        {t('system.storage')}
      </Typography>
      <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap', mb: 3 }}>
        <Paper sx={{ p: 2, flex: 1, minWidth: 160 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('storage.totalStorage')}
          </Typography>
          <Typography variant="h5">{formatBytes(totalSize)}</Typography>
        </Paper>
        <Paper sx={{ p: 2, flex: 1, minWidth: 160 }}>
          <Typography variant="subtitle2" gutterBottom>
            {t('storage.totalFiles')}
          </Typography>
          <Typography variant="h5">{totalFiles}</Typography>
        </Paper>
      </Box>
      <Paper sx={{ p: 2 }}>
        <Typography variant="h6" gutterBottom>
          {t('storage.usageOverTime')}
        </Typography>
        {chartData.length > 0 ? (
          <Box sx={{ width: '100%', height: 400 }}>
            <BarChart
              dataset={chartData}
              series={[
                {
                  dataKey: 'size',
                  label: t('storage.storageMb'),
                  color: '#2dd4bf',
                  valueFormatter: (value) => `${value} MB`,
                },
              ]}
              xAxis={[{ dataKey: 'date', scaleType: 'band' }]}
              yAxis={[{ label: t('storage.storageMb') }]}
              height={350}
            />
          </Box>
        ) : (
          <Typography color="text.secondary">
            {t('storage.noStorageData')}
          </Typography>
        )}
      </Paper>
    </Box>
  );
};
