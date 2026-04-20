import { useState, useMemo } from 'react';
import { LineChart } from '@mui/x-charts/LineChart';
import { OverviewTopSpecies } from '../../types';
import { useTheme } from '@mui/material/styles';
import Box from '@mui/material/Box';
import FormControl from '@mui/material/FormControl';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { labelToUniqueHexColor } from '../../util';

interface HourlyActivityChartProps {
  data: OverviewTopSpecies[];
}

export const HourlyActivityChart: React.FC<HourlyActivityChartProps> = ({
  data,
}) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const [selectedSpecies, setSelectedSpecies] = useState<number | 'all'>('all');

  const hourlyData = useMemo(() => {
    return Array.from({ length: 24 }, (_, hour) => {
      if (selectedSpecies === 'all') {
        return data.reduce((sum, s) => sum + (s.detections[hour] || 0), 0);
      }
      return data.find((s) => s.id === selectedSpecies)?.detections[hour] || 0;
    });
  }, [data, selectedSpecies]);

  const hours = Array.from(
    { length: 24 },
    (_, i) => `${i.toString().padStart(2, '0')}:00`,
  );

  const chartColor =
    selectedSpecies === 'all'
      ? theme.palette.primary.main
      : labelToUniqueHexColor(
          data.find((s) => s.id === selectedSpecies)?.name || '',
        );

  const series = [
    {
      data: hourlyData,
      color: chartColor,
      yAxisId: 'detections',
      valueFormatter: (v: number | null) =>
        v !== null ? t('commonLabels.detectionsCount', { count: v }) : '',
    },
  ];

  return (
    <Box sx={{ width: '100%', height: '100%' }}>
      <Box sx={{ display: 'flex', gap: 2, alignItems: 'center', mb: 1 }}>
        <FormControl size="small" sx={{ minWidth: 180 }}>
          <Typography variant="caption" color="text.secondary" sx={{ mb: 0.5 }}>
            {t('overviewExtra.hourlyChartSpecies')}
          </Typography>
          <Select
            id="hourly-activity-species-select"
            value={selectedSpecies}
            inputProps={{
              'aria-label': t('overviewExtra.hourlyChartSpecies'),
            }}
            onChange={(e) =>
              setSelectedSpecies(e.target.value as number | 'all')
            }
            displayEmpty
          >
            <MenuItem value="all">{t('overviewExtra.allSpecies')}</MenuItem>
            {data.map((species) => (
              <MenuItem key={species.id} value={species.id}>
                {species.name}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
      </Box>
      <Box sx={{ width: '100%', height: 220 }}>
        <LineChart
          xAxis={[
            {
              data: hours,
              scaleType: 'band',
              tickLabelStyle: { angle: 45, textAnchor: 'start', fontSize: 10 },
            },
          ]}
          yAxis={[
            {
              id: 'detections',
              scaleType: 'linear' as const,
              width: 42,
              valueFormatter: (value: number) => `${value}`,
            },
          ]}
          series={series}
          height={220}
          margin={{
            top: 20,
            bottom: 50,
            left: 48,
            right: 10,
          }}
          hideLegend
        />
      </Box>
    </Box>
  );
};
