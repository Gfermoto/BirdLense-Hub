import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import Grid from '@mui/material/Grid2';
import VideocamOutlined from '@mui/icons-material/VideocamOutlined';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import { BirdIcon } from '../../components/icons/BirdIcon';
import { SpeciesVisit } from '../../types';
import { StatCard } from '../../components/StatCard';
import { formatDuration } from '../../utils/timeUtils';

export const TimelineStats = memo(function TimelineStats({ visits }: { visits: SpeciesVisit[] }) {
  const { t } = useTranslation();
  const uniqueSpecies = new Set(visits.map((visit) => visit.species.id)).size;
  const totalDetections = visits.reduce(
    (acc, visit) => acc + visit.max_simultaneous,
    0,
  );
  const recordingDurationSec = visits.reduce((acc, visit) => {
    const sec =
      visit.video_duration_seconds != null && visit.video_duration_seconds > 0
        ? visit.video_duration_seconds
        : (visit.total_recording_seconds ?? 0);
    return acc + sec;
  }, 0);

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
          icon={VideocamOutlined}
          title={t('timelineStats.totalRecordingTime')}
          value={formatDuration(recordingDurationSec)}
        />
      </Grid>
    </Grid>
  );
});
