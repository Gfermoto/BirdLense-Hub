import { useTranslation } from 'react-i18next';
import Grid from '@mui/material/Grid2';
import TimelapseOutlined from '@mui/icons-material/TimelapseOutlined';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import { BirdIcon } from '../../components/icons/BirdIcon';
import { SpeciesVisit } from '../../types';
import { StatCard } from '../../components/StatCard';

const calculateTotalDurationMin = (data: SpeciesVisit[]) => {
  return Math.round(
    data.reduce((acc, visit) => {
      const start = new Date(visit.start_time).getTime();
      const end = new Date(visit.end_time).getTime();
      return acc + (end - start) / 1000 / 60;
    }, 0),
  );
};

export const TimelineStats = ({ visits }: { visits: SpeciesVisit[] }) => {
  const { t } = useTranslation();
  const uniqueSpecies = new Set(visits.map((visit) => visit.species.id)).size;
  const totalDetections = visits.reduce(
    (acc, visit) => acc + visit.max_simultaneous,
    0,
  );
  const totalDurationMin = calculateTotalDurationMin(visits);

  return (
    <Grid container spacing={3} mb={5}>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          icon={BirdIcon}
          title={t('timelineStats.uniqueSpecies')}
          value={uniqueSpecies}
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          icon={VisibilityOutlined}
          title={t('timelineStats.totalVisits')}
          value={totalDetections}
        />
      </Grid>
      <Grid size={{ xs: 12, sm: 4 }}>
        <StatCard
          icon={TimelapseOutlined}
          title={t('timelineStats.totalDuration')}
          value={`${totalDurationMin}m`}
        />
      </Grid>
    </Grid>
  );
};
