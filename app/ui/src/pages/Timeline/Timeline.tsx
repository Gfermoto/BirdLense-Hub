import { memo } from 'react';
import { useTranslation } from 'react-i18next';
import type { SpeciesVisit } from '../../types';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import { useTheme } from '@mui/material/styles';
import useMediaQuery from '@mui/material/useMediaQuery';
import { VisitCard } from '../../components/VisitCard';
import { formatLocalTime } from '../../util';

/** Вертикальная линия и точка между элементами (замена @mui/lab Timeline без @mui/base). */
function TimelineRail({
  isFirst,
  isLast,
}: {
  isFirst: boolean;
  isLast: boolean;
}) {
  return (
    <Box
      sx={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        width: 24,
        flexShrink: 0,
        mx: { xs: 0, sm: 0 },
      }}
    >
      <Box
        sx={{
          width: 2,
          flex: isFirst ? 0 : 1,
          minHeight: isFirst ? 8 : 0,
          bgcolor: 'divider',
        }}
      />
      <Box
        sx={{
          width: 14,
          height: 14,
          borderRadius: '50%',
          border: 2,
          borderColor: 'primary.main',
          bgcolor: 'background.paper',
          flexShrink: 0,
        }}
      />
      <Box
        sx={{
          width: 2,
          flex: isLast ? 0 : 1,
          minHeight: isLast ? 8 : 0,
          bgcolor: 'divider',
        }}
      />
    </Box>
  );
}

export const Timeline = memo(function Timeline({
  visits,
}: {
  visits: SpeciesVisit[];
}) {
  const { t } = useTranslation();
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

  if (!visits.length) {
    return (
      <Alert severity="info" variant="outlined" sx={{ py: 2 }}>
        {t('timeline.emptyVisits')}
      </Alert>
    );
  }

  return (
    <Box
      component="ul"
      sx={{
        listStyle: 'none',
        p: 0,
        m: 0,
        py: isMobile ? 1 : 2,
      }}
    >
      {visits.map((visit, index) => {
        const timeLabel = (
          <Typography variant="body2" color="text.secondary">
            {formatLocalTime(visit.start_time)}
          </Typography>
        );
        const card = (
          <VisitCard visit={visit} compact={isMobile} showDateTime={isMobile} />
        );
        const isFirst = index === 0;
        const isLast = index === visits.length - 1;

        if (isMobile) {
          return (
            <Box
              key={visit.id}
              component="li"
              sx={{
                display: 'flex',
                gap: 1.5,
                alignItems: 'flex-start',
                mb: 1,
              }}
            >
              <TimelineRail isFirst={isFirst} isLast={isLast} />
              <Box sx={{ flex: 1, minWidth: 0 }}>{card}</Box>
            </Box>
          );
        }

        const timeCell = (
          <Box
            sx={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              minWidth: 0,
              py: 1,
              justifyContent: index % 2 === 0 ? 'flex-end' : 'flex-start',
              pr: index % 2 === 0 ? 2 : 0,
              pl: index % 2 === 0 ? 0 : 2,
            }}
          >
            {timeLabel}
          </Box>
        );

        const cardCell = (
          <Box
            data-testid={`timeline-card-shell-${visit.id}`}
            sx={{ width: '100%', minWidth: 0 }}
          >
            {card}
          </Box>
        );

        return (
          <Box
            key={visit.id}
            component="li"
            sx={{
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'stretch',
              width: '100%',
            }}
          >
            {index % 2 === 0 ? (
              <>
                {timeCell}
                <TimelineRail isFirst={isFirst} isLast={isLast} />
                <Box sx={{ flex: 1, pl: 2, py: 1, minWidth: 0 }}>
                  {cardCell}
                </Box>
              </>
            ) : (
              <>
                <Box
                  sx={{
                    flex: 1,
                    pr: 2,
                    py: 1,
                    minWidth: 0,
                    display: 'flex',
                    justifyContent: 'flex-end',
                  }}
                >
                  {cardCell}
                </Box>
                <TimelineRail isFirst={isFirst} isLast={isLast} />
                {timeCell}
              </>
            )}
          </Box>
        );
      })}
    </Box>
  );
});
