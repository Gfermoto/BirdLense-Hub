import React from 'react';
import { useTranslation } from 'react-i18next';
import { PieChart } from '@mui/x-charts/PieChart';
import { OverviewTopSpecies } from '../../types';
import { labelToUniqueHexColor } from '../../util';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import dayjs, { Dayjs } from 'dayjs';
import { useNavigate } from 'react-router-dom';

interface SpeciesDistributionChartProps {
  data: OverviewTopSpecies[];
  date?: Dayjs;
  /** Совпадает с DailyPatternChart на Overview (по умолчанию 450). */
  size?: number;
}

export const SpeciesDistributionChart: React.FC<
  SpeciesDistributionChartProps
> = ({ data, date, size: propSize }) => {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
  const navigate = useNavigate();
  const desktopSize = propSize ?? 450;
  const chartSize = isMobile ? Math.min(typeof window !== 'undefined' ? window.innerWidth * 0.8 : 280, 400) : desktopSize;
  const scale = chartSize / 400;
  const outerRadius = isMobile ? 104 : Math.round(150 * scale);
  const innerRadius = isMobile ? 34 : Math.round(50 * scale);
  const pieData = data
    .map((species) => ({
      id: species.id,
      value: species.detections.reduce((a, b) => a + b, 0),
      label: '',
      name: species.name,
      color: labelToUniqueHexColor(species.name),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value);

  const navigateToTimelineForSpecies = (speciesId: number) => {
    const dateValue = (date ?? dayjs()).format('YYYY-MM-DD');
    navigate(`/timeline?speciesId=${speciesId}&date=${dateValue}`);
  };

  if (pieData.length === 0) {
    return (
      <Box
        sx={{
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Typography color="text.secondary">{t('common.noData')}</Typography>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        boxSizing: 'border-box',
      }}
    >
      <Box
        sx={{
          width: chartSize,
          height: chartSize,
          maxWidth: '100%',
          position: 'relative',
          margin: 'auto',
          flexShrink: 0,
        }}
      >
      <PieChart
        hideLegend
        series={[
          {
            data: pieData,
            highlightScope: { faded: 'global', highlighted: 'item' },
            faded: { innerRadius: 24, additionalRadius: -18, color: 'gray' },
            innerRadius,
            outerRadius,
            paddingAngle: 2,
            cornerRadius: 4,
          },
        ]}
        width={chartSize}
        height={chartSize}
        onItemClick={(_, item) => {
          if (typeof item.dataIndex !== 'number') return;
          const selected = pieData[item.dataIndex];
          if (!selected) return;
          navigateToTimelineForSpecies(Number(selected.id));
        }}
        margin={{ top: 8, bottom: 8, left: 8, right: 8 }}
      />
      </Box>
      <Box
        sx={{
          width: '100%',
          maxWidth: '100%',
          minWidth: 0,
          display: 'flex',
          flexDirection: 'row',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: 2,
          p: 1,
          flexShrink: 0,
          boxSizing: 'border-box',
        }}
      >
        {pieData.map((item) => (
          <Box
            key={String(item.id)}
            data-testid="overview-species-legend-chip"
            onClick={() => navigateToTimelineForSpecies(Number(item.id))}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                navigateToTimelineForSpecies(Number(item.id));
              }
            }}
            role="button"
            tabIndex={0}
            aria-label={item.name}
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 1,
              maxWidth: '100%',
              minWidth: 0,
              px: 0.5,
              py: 0.25,
              cursor: 'pointer',
              '&:hover': { opacity: 0.85 },
              '&:focus-visible': {
                outline: '2px solid #5EEAD4',
                outlineOffset: 2,
              },
            }}
          >
            <Box
              sx={{
                width: 16,
                height: 16,
                flexShrink: 0,
                backgroundColor: item.color,
              }}
            />
            <Typography
              variant="caption"
              sx={{
                maxWidth: { xs: 'min(100%, 220px)', sm: 280 },
                overflowWrap: 'anywhere',
                textAlign: 'center',
              }}
            >
              {item.name} ({item.value})
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};
