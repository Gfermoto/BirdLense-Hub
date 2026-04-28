import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import type { SxProps, Theme } from '@mui/material/styles';
import dayjs from 'dayjs';
import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  useLocation,
  useNavigate,
  useSearchParams,
} from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { fetchOverviewData } from '../api/speciesOverviewDetections';
import {
  fetchUnknownsForObserverDate,
} from '../api/timeline';
import { queryKeys } from '../api/queryKeys';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';

export type RecordingsModeSwitcherProps = {
  sx?: SxProps<Theme>;
};

/**
 * Единый переключатель режимов раздела «Записи»: лента / каталог избранного / на проверке.
 * Используется на `/timeline`, `/favorites` и в режиме review на таймлайне.
 */
export function RecordingsModeSwitcher({ sx }: RecordingsModeSwitcherProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    canEdit,
    isLoading: accessContextLoading,
  } = useProtectedArea();
  const showReviewModeEntry = canEdit || accessContextLoading;

  const isReviewMode = searchParams.get('review') === '1';
  const isFavoritesTimeline =
    searchParams.get('favorites') === '1' ||
    searchParams.get('favorite_only') === '1';
  const isPlainTimeline =
    pathname === '/timeline' &&
    !isReviewMode &&
    !isFavoritesTimeline;

  const isFavoritesActive =
    pathname === '/favorites' ||
    (pathname === '/timeline' && isFavoritesTimeline && !isReviewMode);

  const { data: observerOverview } = useQuery({
    queryKey: queryKeys.timeline.observerTimezone,
    queryFn: () => fetchOverviewData(dayjs().format('YYYY-MM-DD')),
    staleTime: 1000 * 60 * 30,
  });

  const observerToday = useMemo(() => {
    const timezone = observerOverview?.observer_timezone;
    if (!timezone) {
      return dayjs().startOf('day');
    }
    try {
      const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: timezone,
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
      }).formatToParts(new Date());
      const year = parts.find((part) => part.type === 'year')?.value;
      const month = parts.find((part) => part.type === 'month')?.value;
      const day = parts.find((part) => part.type === 'day')?.value;
      if (!year || !month || !day) {
        return dayjs().startOf('day');
      }
      return dayjs(`${year}-${month}-${day}`).startOf('day');
    } catch {
      return dayjs().startOf('day');
    }
  }, [observerOverview?.observer_timezone]);

  const { data: unknownsCount = 0 } = useQuery({
    queryKey: queryKeys.timeline.unknownsCount(
      observerToday.format('YYYY-MM-DD'),
      'all',
      null,
    ),
    queryFn: async () => {
      const rows = await fetchUnknownsForObserverDate(
        observerToday.format('YYYY-MM-DD'),
        { timeOfDay: 'all', limit: 500 },
      );
      return rows.length;
    },
    enabled: showReviewModeEntry,
  });

  const goPlainTimeline = () => {
    if (pathname === '/favorites') {
      navigate('/timeline');
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete('review');
    next.delete('favorites');
    next.delete('favorite_only');
    setSearchParams(next, { replace: true });
  };

  const goFavoritesCatalog = () => {
    navigate('/favorites');
  };

  const goReview = () => {
    if (pathname === '/favorites') {
      navigate('/timeline?review=1');
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.set('review', '1');
    next.delete('favorites');
    next.delete('favorite_only');
    setSearchParams(next, { replace: true });
  };

  return (
    <Box
      role="group"
      aria-label={t('timeline.modeSwitcherAria')}
      display="flex"
      gap={1}
      alignItems="center"
      sx={{ mb: 2, ...sx }}
    >
      <Chip
        color={isPlainTimeline ? 'primary' : 'default'}
        variant={isPlainTimeline ? 'filled' : 'outlined'}
        label={t('timeline.modeTimeline')}
        aria-pressed={isPlainTimeline}
        onClick={goPlainTimeline}
      />
      <Chip
        color={isFavoritesActive ? 'primary' : 'default'}
        variant={isFavoritesActive ? 'filled' : 'outlined'}
        label={t('timeline.modeFavorites')}
        aria-pressed={isFavoritesActive}
        onClick={goFavoritesCatalog}
      />
      {showReviewModeEntry ? (
        <Chip
          color={isReviewMode ? 'primary' : 'default'}
          variant={isReviewMode ? 'filled' : 'outlined'}
          aria-pressed={isReviewMode}
          onClick={goReview}
          sx={{ px: 0.5 }}
          label={
            <Box
              component="span"
              sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.75 }}
            >
              <Box component="span">{t('timeline.modeReview')}</Box>
              {unknownsCount > 0 && (
                <Box
                  component="span"
                  sx={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    minWidth: 20,
                    height: 20,
                    px: 0.75,
                    borderRadius: 10,
                    bgcolor: 'warning.main',
                    color: 'warning.contrastText',
                    fontSize: 12,
                    fontWeight: 700,
                    lineHeight: 1,
                  }}
                >
                  {Math.min(unknownsCount, 500)}
                </Box>
              )}
            </Box>
          }
        />
      ) : null}
    </Box>
  );
}
