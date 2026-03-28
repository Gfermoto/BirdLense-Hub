import React from 'react';
import { useTranslation } from 'react-i18next';
import { PieChart } from '@mui/x-charts/PieChart';
import { OverviewTopSpecies } from '../../types';
import { labelToUniqueHexColor } from '../../util';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import dayjs, { Dayjs } from 'dayjs';
import { useNavigate } from 'react-router-dom';

interface SpeciesDistributionChartProps {
  data: OverviewTopSpecies[];
  date?: Dayjs;
}

export const SpeciesDistributionChart: React.FC<
  SpeciesDistributionChartProps
> = ({ data, date }) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const pieData = data
    .map((species) => ({
      id: species.id,
      value: species.detections.reduce((a, b) => a + b, 0),
      label: species.name,
      color: labelToUniqueHexColor(species.name),
    }))
    .filter((item) => item.value > 0)
    .sort((a, b) => b.value - a.value);

  const navigateToTimelineForSpecies = (speciesId: number) => {
    const dateValue = (date ?? dayjs()).startOf('day').toISOString();
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
        height: '100%',
        minHeight: 400,
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
      }}
    >
      <PieChart
        series={[
          {
            data: pieData,
            highlightScope: { faded: 'global', highlighted: 'item' },
            faded: { innerRadius: 30, additionalRadius: -30, color: 'gray' },
            innerRadius: 50,
            outerRadius: 150,
            paddingAngle: 2,
            cornerRadius: 4,
          },
        ]}
        width={400}
        height={400}
        onItemClick={(_, item) => {
          if (typeof item.dataIndex !== 'number') return;
          const selected = pieData[item.dataIndex];
          if (!selected) return;
          navigateToTimelineForSpecies(Number(selected.id));
        }}
        slotProps={{
          legend: {
            hidden: true,
          },
        }}
        margin={{ top: 20, bottom: 20, left: 20, right: 20 }}
      />
      <Box
        sx={{
          mt: 1,
          px: 2,
          width: '100%',
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'center',
          gap: 1.5,
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
            aria-label={item.label}
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 1,
              px: 1.25,
              py: 0.5,
              borderRadius: 999,
              border: 1,
              borderColor: 'divider',
              cursor: 'pointer',
              '&:hover': { bgcolor: 'action.hover' },
              '&:focus-visible': {
                outline: '2px solid #5EEAD4',
                outlineOffset: 2,
              },
            }}
          >
            <Box
              sx={{
                width: 12,
                height: 12,
                borderRadius: '50%',
                backgroundColor: item.color,
              }}
            />
            <Typography variant="caption">
              {item.label} ({item.value})
            </Typography>
          </Box>
        ))}
      </Box>
    </Box>
  );
};
