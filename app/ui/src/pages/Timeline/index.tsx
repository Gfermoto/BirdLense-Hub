import { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { Timeline } from './Timeline';
import { TimelineStats } from './TimelineStats';
import { SpeciesVisit, Species } from '../../types';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import type { SelectChangeEvent } from '@mui/material/Select';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import DownloadIcon from '@mui/icons-material/Download';
import ChevronLeftIcon from '@mui/icons-material/ChevronLeft';
import ChevronRightIcon from '@mui/icons-material/ChevronRight';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { getApiErrorMessage } from '../../api/api';
import {
  exportTimelineForObserverDate,
  fetchTimelineForObserverDate,
  fetchUnknownsForObserverDate,
} from '../../api/timeline';
import { fetchNearestRecordingDay } from '../../api/video';
import { fetchOverviewData } from '../../api/speciesOverviewDetections';
import { queryKeys } from '../../api/queryKeys';
import OutlinedInput from '@mui/material/OutlinedInput';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import { PageHelp } from '../../components/PageHelp';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { timelineHelpConfig } from '../../page-help-config';
import { type TimeOfDay } from '../../utils/timeUtils';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import Chip from '@mui/material/Chip';
import { UnknownsPage } from '../Unknowns';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import Snackbar from '@mui/material/Snackbar';

function useSpeciesList(visits: SpeciesVisit[] | undefined) {
  return visits
    ? visits.reduce((acc: Partial<Species>[], visit) => {
        const sp = visit.species;
        if (!sp?.name) return acc;
        if (!acc.some((existing) => existing.name === sp.name)) {
          acc.push(sp);
        }
        return acc;
      }, [])
    : [];
}

function useFilteredVisits(
  visits: SpeciesVisit[] | undefined,
  selectedSpeciesIds: number[],
) {
  return visits?.filter(
    (visit) =>
      selectedSpeciesIds.length === 0 ||
      selectedSpeciesIds.includes(visit.species.id),
  );
}

function parseHourFromSearchParams(
  searchParams: URLSearchParams,
): number | null {
  const hp = searchParams.get('hour');
  if (hp != null && hp !== '') {
    const p = parseInt(hp, 10);
    if (Number.isFinite(p) && p >= 0 && p <= 23) return p;
  }
  const paramDate = searchParams.get('date');
  if (paramDate && /T/.test(paramDate)) {
    return dayjs(paramDate).hour();
  }
  return null;
}

export function TimelinePage() {
  const { t } = useTranslation();
  const {
    canEdit,
    role,
    requiresPassword,
    isLoading: accessContextLoading,
  } = useProtectedArea();
  /** Пока контекст доступа грузится — не прячем чип (избегаем мигания у вошедших по cookie). */
  const showReviewModeEntry = canEdit || accessContextLoading;
  /** Только админ: оператор не ходит в Библиотеку — подсказка про скан диска ему не нужна. */
  const showLibraryDiskScanHint = canEdit && role === 'admin';
  /** Только после входа админа или оператора, если включён пароль (не гостю с улицы). */
  const showReportsAndSharingHint =
    requiresPassword && canEdit && (role === 'admin' || role === 'contributor');
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const isReviewMode = searchParams.get('review') === '1';
  const isFavoritesMode =
    searchParams.get('favorites') === '1' ||
    searchParams.get('favorite_only') === '1';
  const isPlainTimeline = !isReviewMode && !isFavoritesMode;

  useEffect(() => {
    if (accessContextLoading || canEdit || !isReviewMode) return;
    navigate('/timeline', { replace: true });
  }, [accessContextLoading, canEdit, isReviewMode, navigate]);

  useDocumentTitle(
    isReviewMode
      ? t('timeline.modeReview')
      : isFavoritesMode
        ? t('timeline.modeFavorites')
        : t('nav.timeline'),
  );
  const filterHour = useMemo(
    () => parseHourFromSearchParams(searchParams),
    [searchParams],
  );
  const [selectedSpeciesIds, setSelectedSpeciesIds] = useState<number[]>([]);
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>('all');
  const [exportAnchor, setExportAnchor] = useState<null | HTMLElement>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const selectedDate = useMemo(() => {
    const paramDate = searchParams.get('date');
    const parsed = paramDate
      ? dayjs(paramDate).startOf('date')
      : dayjs().startOf('date');
    return parsed.isValid() ? parsed : dayjs().startOf('date');
  }, [searchParams]);
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

  const {
    data: visits,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: queryKeys.timeline.speciesVisits(
      selectedDate?.format('YYYY-MM-DD') ?? '',
      timeOfDay,
      filterHour,
      isFavoritesMode,
    ),
    queryFn: () => {
      if (!selectedDate) return [];
      const base = filterHour !== null ? { hour: filterHour } : { timeOfDay };
      return fetchTimelineForObserverDate(selectedDate.format('YYYY-MM-DD'), {
        ...base,
        favoritesOnly: isFavoritesMode,
      });
    },
    enabled: !isReviewMode,
  });

  const { data: unknownsCount = 0 } = useQuery({
    queryKey: queryKeys.timeline.unknownsCount(
      selectedDate?.format('YYYY-MM-DD') ?? '',
      timeOfDay,
      filterHour,
    ),
    queryFn: async () => {
      if (!selectedDate) return 0;
      const rows = await fetchUnknownsForObserverDate(
        selectedDate.format('YYYY-MM-DD'),
        filterHour !== null
          ? { hour: filterHour, limit: 500 }
          : { timeOfDay, limit: 500 },
      );
      return rows.length;
    },
    enabled: showReviewModeEntry,
  });

  useEffect(() => {
    if (visits) {
      const speciesId = Number(searchParams.get('speciesId'));
      if (speciesId) {
        const childSpeciesIds = [
          ...new Set(
            visits
              .map((visit) => visit.species)
              .filter(
                (species) =>
                  species.id === speciesId || species.parent_id === speciesId,
              )
              .map((species) => species.id),
          ),
        ];
        if (childSpeciesIds.length > 0) {
          setSelectedSpeciesIds(childSpeciesIds);
        }
      }
    }
  }, [searchParams, visits]);

  const updateSelectedDate = useCallback(
    (nextDate: Dayjs | null) => {
      if (!nextDate) {
        return;
      }
      const normalizedDate = nextDate.startOf('day');
      const formattedDate = normalizedDate.format('YYYY-MM-DD');
      if (searchParams.get('date') === formattedDate) {
        return;
      }
      const next = new URLSearchParams(searchParams);
      next.set('date', formattedDate);
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const jumpToNearestRecordingDay = useCallback(
    async (direction: 'prev' | 'next') => {
      const currentDate = selectedDate.format('YYYY-MM-DD');
      const result = await fetchNearestRecordingDay(currentDate, direction);
      if (result.found && result.date) {
        updateSelectedDate(dayjs(result.date));
      }
    },
    [selectedDate, updateSelectedDate],
  );

  const speciesList = useSpeciesList(visits);
  const filteredVisits = useFilteredVisits(visits, selectedSpeciesIds);

  const handleSpeciesChange = (event: SelectChangeEvent<number[]>) => {
    const value = event.target.value;
    setSelectedSpeciesIds(
      typeof value === 'string'
        ? value.split(',').map(Number)
        : value.map(Number),
    );
  };

  const clearHourFilter = () => {
    const next = new URLSearchParams(searchParams);
    next.delete('hour');
    setSearchParams(next, { replace: true });
  };

  const handleExport = async (format: 'csv' | 'json' | 'ebird') => {
    if (!selectedDate) return;
    setExportAnchor(null);
    setExportError(null);
    setExporting(true);
    try {
      await exportTimelineForObserverDate(
        selectedDate.format('YYYY-MM-DD'),
        format,
        {
          ...(filterHour !== null ? { hour: filterHour } : { timeOfDay }),
          favoritesOnly: isFavoritesMode,
        },
      );
    } catch (err) {
      console.error('Export failed:', err);
      setExportError(getApiErrorMessage(err, t('timeline.exportFailed')));
    } finally {
      setExporting(false);
    }
  };

  if (!isReviewMode && isLoading)
    return <PageLoadingState label={t('common.loading')} />;
  if (isReviewMode && !canEdit)
    return <PageLoadingState label={t('common.loading')} />;
  if (!isReviewMode && error)
    return (
      <PageMessageState
        title={t('nav.timeline')}
        message={t('timeline.errorLoad')}
        severity="error"
        action={
          <Button variant="outlined" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );

  const timelineModeSwitcher = (
    <Box
      role="group"
      aria-label={t('timeline.modeSwitcherAria')}
      display="flex"
      gap={1}
      alignItems="center"
      sx={{ mb: 2 }}
    >
      <Chip
        color={isPlainTimeline ? 'primary' : 'default'}
        variant={isPlainTimeline ? 'filled' : 'outlined'}
        label={t('timeline.modeTimeline')}
        aria-pressed={isPlainTimeline}
        onClick={() => {
          const next = new URLSearchParams(searchParams);
          next.delete('review');
          next.delete('favorites');
          next.delete('favorite_only');
          setSearchParams(next, { replace: true });
        }}
      />
      <Chip
        color={isFavoritesMode && !isReviewMode ? 'primary' : 'default'}
        variant={isFavoritesMode && !isReviewMode ? 'filled' : 'outlined'}
        label={t('timeline.modeFavorites')}
        aria-pressed={isFavoritesMode && !isReviewMode}
        onClick={() => {
          navigate('/favorites');
        }}
      />
      {showReviewModeEntry ? (
        <Chip
          color={isReviewMode ? 'primary' : 'default'}
          variant={isReviewMode ? 'filled' : 'outlined'}
          aria-pressed={isReviewMode}
          onClick={() => {
            const next = new URLSearchParams(searchParams);
            next.set('review', '1');
            next.delete('favorites');
            next.delete('favorite_only');
            setSearchParams(next, { replace: true });
          }}
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

  return (
    <>
      {isReviewMode ? (
        <UnknownsPage afterTitleSlot={timelineModeSwitcher} />
      ) : (
        <>
          <PageHelp {...timelineHelpConfig} />
          {timelineModeSwitcher}
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ mb: showReportsAndSharingHint ? 1 : 2 }}
          >
            {isFavoritesMode
              ? t('timeline.favoritesIntro')
              : t('timeline.intro')}
          </Typography>
          {showReportsAndSharingHint ? (
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('timeline.reportsAndSharingHint')}
            </Typography>
          ) : null}
          {filterHour !== null && (
            <Chip
              label={t('timeline.hourFilterChip', {
                from: `${String(filterHour).padStart(2, '0')}:00`,
                to: `${String(filterHour).padStart(2, '0')}:59`,
              })}
              onDelete={clearHourFilter}
              sx={{ mb: 2 }}
              color="secondary"
              variant="outlined"
            />
          )}
          {showLibraryDiskScanHint && (
            <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
              {t('timeline.noRecords')}{' '}
              <Button
                component={Link}
                to="/library#recordings"
                size="small"
                startIcon={<FolderOpenIcon />}
                sx={{ verticalAlign: 'baseline' }}
              >
                {t('timeline.scanImport')}
              </Button>{' '}
              {t('timeline.scanHint')}.
            </Alert>
          )}
          <Box
            sx={{
              display: 'grid',
              gridTemplateColumns: {
                xs: 'auto minmax(0, 1fr) auto',
                md: 'auto minmax(220px, 280px) auto minmax(180px, 220px) minmax(220px, 1fr) auto',
              },
              alignItems: 'center',
              gap: 2,
              mb: 4,
            }}
          >
            <Tooltip title={t('timeline.previousDay')}>
              <span>
                <IconButton
                  aria-label={t('timeline.previousDay')}
                  onClick={() => void jumpToNearestRecordingDay('prev')}
                >
                  <ChevronLeftIcon />
                </IconButton>
              </span>
            </Tooltip>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <DatePicker
                label={t('timeline.selectDate')}
                value={selectedDate}
                onChange={updateSelectedDate}
                maxDate={observerToday}
                slotProps={{
                  textField: {
                    fullWidth: true,
                  },
                }}
              />
            </LocalizationProvider>
            <Tooltip title={t('timeline.nextDay')}>
              <span>
                <IconButton
                  aria-label={t('timeline.nextDay')}
                  disabled={!selectedDate.isBefore(observerToday, 'day')}
                  onClick={() => void jumpToNearestRecordingDay('next')}
                >
                  <ChevronRightIcon />
                </IconButton>
              </span>
            </Tooltip>
            <FormControl
              sx={{
                minWidth: 0,
                gridColumn: { xs: '1 / span 3', md: '4' },
              }}
            >
              <InputLabel id="timeofday-label">
                {t('timeline.timeOfDay')}
              </InputLabel>
              <Select
                labelId="timeofday-label"
                value={timeOfDay}
                disabled={filterHour !== null}
                onChange={(e) => {
                  setTimeOfDay(e.target.value as TimeOfDay);
                  if (searchParams.get('hour')) {
                    const next = new URLSearchParams(searchParams);
                    next.delete('hour');
                    setSearchParams(next, { replace: true });
                  }
                }}
                label={t('timeline.timeOfDay')}
              >
                <MenuItem value="all">{t('timeline.timeAllDay')}</MenuItem>
                <MenuItem value="night">{t('timeline.timeNight')}</MenuItem>
                <MenuItem value="morning">{t('timeline.timeMorning')}</MenuItem>
                <MenuItem value="day">{t('timeline.timeDay')}</MenuItem>
                <MenuItem value="afternoon">
                  {t('timeline.timeAfternoon')}
                </MenuItem>
                <MenuItem value="evening">{t('timeline.timeEvening')}</MenuItem>
              </Select>
            </FormControl>
            <FormControl
              sx={{
                minWidth: 0,
                gridColumn: { xs: '1 / span 3', md: '5' },
              }}
            >
              <InputLabel id="species-select-label">
                {t('timeline.species')}
              </InputLabel>
              <Select
                labelId="species-select-label"
                multiple
                value={selectedSpeciesIds}
                onChange={handleSpeciesChange}
                input={<OutlinedInput label={t('timeline.species')} />}
                renderValue={(selected) =>
                  selected.length === 0
                    ? t('common.all')
                    : speciesList
                        .filter((species) =>
                          selected.includes(Number(species.id)),
                        )
                        .map((species) => species.name)
                        .join(', ')
                }
              >
                {speciesList.map((species) => (
                  <MenuItem key={species.id} value={Number(species.id)}>
                    <Checkbox
                      checked={selectedSpeciesIds.includes(Number(species.id))}
                    />
                    <ListItemText primary={species.name} />
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <Box
              sx={{
                gridColumn: { xs: '1 / span 3', md: '6' },
                justifySelf: { xs: 'end', md: 'start' },
              }}
            >
              <Tooltip
                title={
                  !canEdit
                    ? t('common.loginRequiredForExport')
                    : t('timeline.export')
                }
              >
                <span>
                  <IconButton
                    onClick={(e) => setExportAnchor(e.currentTarget)}
                    disabled={exporting || !canEdit}
                    aria-label={t('timeline.export')}
                    data-testid="timeline-export-menu-trigger"
                  >
                    <DownloadIcon />
                  </IconButton>
                </span>
              </Tooltip>
            </Box>
            <Menu
              anchorEl={exportAnchor}
              open={!!exportAnchor}
              onClose={() => setExportAnchor(null)}
              anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
              transformOrigin={{ vertical: 'top', horizontal: 'right' }}
            >
              <MenuItem onClick={() => handleExport('csv')}>
                {t('timeline.exportCsv')}
              </MenuItem>
              <MenuItem onClick={() => handleExport('json')}>
                {t('timeline.exportJson')}
              </MenuItem>
              <MenuItem onClick={() => handleExport('ebird')}>
                {t('timeline.exportEbird')}
              </MenuItem>
            </Menu>
          </Box>

          <TimelineStats visits={filteredVisits ?? []} />
          <Divider sx={{ marginBottom: 4 }} />
          <Timeline visits={filteredVisits ?? []} />
        </>
      )}
      <Snackbar
        open={!!exportError}
        autoHideDuration={8000}
        onClose={() => setExportError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setExportError(null)}
          severity="error"
          variant="filled"
          elevation={6}
          sx={{ width: '100%' }}
          data-testid="timeline-export-error"
          role="alert"
          aria-live="assertive"
        >
          {exportError}
        </Alert>
      </Snackbar>
    </>
  );
}

export default TimelinePage;
