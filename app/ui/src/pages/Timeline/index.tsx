import { useState, useEffect, useMemo, useCallback, useRef } from 'react';
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
import { BirdProfileFilterAutocomplete } from '../../components/filters/BirdProfileFilterAutocomplete';
import { BehaviorFilterSelect } from '../../components/filters/BehaviorFilterSelect';
import { BirdProfilesCatalogDialog } from '../../components/BirdProfilesCatalogDialog';
import FormatListBulletedIcon from '@mui/icons-material/FormatListBulleted';
import { fetchBirdProfiles } from '../../api/speciesOverviewDetections';
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
} from '../../api/timeline';
import { fetchNearestRecordingDay } from '../../api/video';
import {
  fetchBirdDirectory,
  fetchOverviewData,
  speciesDirectoryItems,
} from '../../api/speciesOverviewDetections';
import { fetchStatus } from '../../api/camerasHealth';
import { fetchSystemMetricsLive } from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import OutlinedInput from '@mui/material/OutlinedInput';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import Stack from '@mui/material/Stack';
import { PageHelp } from '../../components/PageHelp';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { timelineHelpConfig } from '../../page-help-config';
import { type TimeOfDay } from '../../utils/timeUtils';
import {
  getVisitNickname,
  getVisitBehaviorSortValue,
  visitMatchesBehavior,
  visitMatchesBirdProfile,
} from './timelineFilters';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import Chip from '@mui/material/Chip';
import { UnknownsPage } from '../Unknowns';
import { RecordingsModeSwitcher } from '../../components/RecordingsModeSwitcher';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import Snackbar from '@mui/material/Snackbar';

function useSpeciesList(
  catalogSpecies: Partial<Species>[] | undefined,
  visits: SpeciesVisit[] | undefined,
) {
  if (catalogSpecies && catalogSpecies.length > 0) {
    return catalogSpecies;
  }
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

type TimelineSortBy =
  | 'date_desc'
  | 'date_asc'
  | 'species'
  | 'nickname'
  | 'confidence'
  | 'duration'
  | 'behavior';
type TimelineTriggerSource =
  | 'all'
  | 'opencv'
  | 'frigate'
  | 'motion_sensor'
  | 'scales';

function getVisitMaxConfidence(visit: SpeciesVisit): number {
  const detections = visit.detections ?? [];
  if (detections.length === 0) return 0;
  return Math.max(...detections.map((d) => Number(d.confidence) || 0));
}

function getVisitDurationSeconds(visit: SpeciesVisit): number {
  if (visit.video_duration_seconds != null && visit.video_duration_seconds > 0) {
    return visit.video_duration_seconds;
  }
  return visit.total_recording_seconds ?? 0;
}

function parseBirdProfileIdFromSearchParams(
  searchParams: URLSearchParams,
): number | null {
  const raw = searchParams.get('bird_profile_id');
  if (!raw) return null;
  const parsed = Number(raw);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
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
  const { t, i18n } = useTranslation();
  const {
    canEdit,
    role,
    requiresPassword,
    isLoading: accessContextLoading,
  } = useProtectedArea();
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
  const [birdProfileFilterId, setBirdProfileFilterId] = useState<number | null>(
    () => parseBirdProfileIdFromSearchParams(searchParams),
  );
  const [behaviorFilter, setBehaviorFilter] = useState(
    () => searchParams.get('behavior')?.trim() ?? '',
  );
  const [triggerSource, setTriggerSource] =
    useState<TimelineTriggerSource>('all');
  const [sortBy, setSortBy] = useState<TimelineSortBy>('date_desc');
  const [exportAnchor, setExportAnchor] = useState<null | HTMLElement>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [birdCatalogOpen, setBirdCatalogOpen] = useState(false);
  const [jumpPending, setJumpPending] = useState(false);
  const jumpRequestSeqRef = useRef(0);
  const selectedDate = useMemo(() => {
    const paramDate = searchParams.get('date');
    const parsed = paramDate
      ? dayjs(paramDate).startOf('date')
      : dayjs().startOf('date');
    return parsed.isValid() ? parsed : dayjs().startOf('date');
  }, [searchParams]);
  const { data: birdProfilesForFilter = [] } = useQuery({
    queryKey: ['bird-profiles', 'timeline-filter-map'],
    queryFn: async () => (await fetchBirdProfiles({ limit: 200 })).items,
    staleTime: 1000 * 60 * 5,
    enabled: !isReviewMode,
  });
  const birdProfilesById = useMemo(
    () => new Map(birdProfilesForFilter.map((profile) => [Number(profile.id), profile])),
    [birdProfilesForFilter],
  );

  const updateBirdProfileFilter = useCallback(
    (profileId: number | null) => {
      setBirdProfileFilterId(profileId);
      const next = new URLSearchParams(searchParams);
      if (profileId) {
        next.set('bird_profile_id', String(profileId));
      } else {
        next.delete('bird_profile_id');
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  const updateBehaviorFilter = useCallback(
    (behavior: string) => {
      setBehaviorFilter(behavior);
      const next = new URLSearchParams(searchParams);
      if (behavior) {
        next.set('behavior', behavior);
      } else {
        next.delete('behavior');
      }
      setSearchParams(next, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  useEffect(() => {
    setBirdProfileFilterId(parseBirdProfileIdFromSearchParams(searchParams));
    setBehaviorFilter(searchParams.get('behavior')?.trim() ?? '');
  }, [searchParams]);

  const { data: observerOverview } = useQuery({
    queryKey: queryKeys.timeline.observerTimezone,
    queryFn: () => fetchOverviewData(dayjs().format('YYYY-MM-DD')),
    staleTime: 1000 * 60 * 30,
  });
  const { data: systemMetricsLive } = useQuery({
    queryKey: queryKeys.system.metricsLive,
    queryFn: fetchSystemMetricsLive,
    staleTime: 30_000,
    refetchInterval: 30_000,
    retry: 1,
  });
  const { data: statusData } = useQuery({
    queryKey: queryKeys.health.status,
    queryFn: fetchStatus,
    staleTime: 30_000,
    refetchInterval: 30_000,
    retry: 1,
  });
  const activeTriggerSources = useMemo(() => {
    const raw = statusData?.active_triggers;
    if (!Array.isArray(raw)) return [] as TimelineTriggerSource[];
    const allowed = new Set<TimelineTriggerSource>([
      'opencv',
      'frigate',
      'motion_sensor',
      'scales',
    ]);
    return raw
      .map((x) => String(x || '').trim().toLowerCase())
      .filter(
        (x): x is TimelineTriggerSource =>
          allowed.has(x as TimelineTriggerSource),
      );
  }, [statusData]);
  const triggerOptions = useMemo(
    () =>
      ([
        { value: 'all', label: t('timeline.triggerSourceAll') },
        { value: 'opencv', label: t('timeline.triggerSourceOpencv') },
        { value: 'frigate', label: t('timeline.triggerSourceFrigate') },
        {
          value: 'motion_sensor',
          label: t('timeline.triggerSourceMotionSensor'),
        },
        { value: 'scales', label: t('timeline.triggerSourceScales') },
      ] as const).filter(
        (opt) =>
          opt.value === 'all' || activeTriggerSources.includes(opt.value),
      ),
    [activeTriggerSources, t],
  );
  useEffect(() => {
    if (triggerSource === 'all') return;
    if (!activeTriggerSources.includes(triggerSource)) {
      setTriggerSource('all');
    }
  }, [activeTriggerSources, triggerSource]);
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
  const { data: timelineSpeciesCatalog = [] } = useQuery({
    queryKey: queryKeys.species.directory,
    queryFn: async () =>
      speciesDirectoryItems(
        await fetchBirdDirectory({
          scope: 'observed',
          meta: false,
        }),
      ),
    staleTime: 1000 * 60 * 5,
    enabled: !isReviewMode,
  });

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
      triggerSource,
    ),
    queryFn: () => {
      if (!selectedDate) return [];
      const base = filterHour !== null ? { hour: filterHour } : { timeOfDay };
      return fetchTimelineForObserverDate(selectedDate.format('YYYY-MM-DD'), {
        ...base,
        favoritesOnly: isFavoritesMode,
        triggerSource,
      });
    },
    enabled: !isReviewMode,
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
      if (jumpPending) return;
      const requestSeq = ++jumpRequestSeqRef.current;
      setJumpPending(true);
      const currentDate = selectedDate.format('YYYY-MM-DD');
      try {
        const result = await fetchNearestRecordingDay(currentDate, direction);
        if (jumpRequestSeqRef.current !== requestSeq) return;
        if (result.found && result.date) {
          updateSelectedDate(dayjs(result.date));
        }
      } finally {
        if (jumpRequestSeqRef.current === requestSeq) {
          setJumpPending(false);
        }
      }
    },
    [jumpPending, selectedDate, updateSelectedDate],
  );

  const speciesList = useSpeciesList(timelineSpeciesCatalog, visits);
  const selectedBySpeciesVisits = useFilteredVisits(visits, selectedSpeciesIds);
  const filteredVisits = useMemo(() => {
    const rows = (selectedBySpeciesVisits ?? []).filter((visit) => {
      if (
        !visitMatchesBirdProfile(visit, birdProfileFilterId, birdProfilesById)
      ) {
        return false;
      }
      if (!visitMatchesBehavior(visit, behaviorFilter)) {
        return false;
      }
      return true;
    });
    const sorted = [...rows];
    sorted.sort((a, b) => {
      const aStart = dayjs(a.start_time).valueOf();
      const bStart = dayjs(b.start_time).valueOf();
      if (sortBy === 'date_asc') {
        return aStart - bStart;
      }
      if (sortBy === 'date_desc') {
        return bStart - aStart;
      }
      if (sortBy === 'species') {
        const cmp = String(a.species?.name || '').localeCompare(
          String(b.species?.name || ''),
          i18n.language,
        );
        return cmp !== 0 ? cmp : bStart - aStart;
      }
      if (sortBy === 'nickname') {
        const cmp = getVisitNickname(a).localeCompare(
          getVisitNickname(b),
          i18n.language,
        );
        return cmp !== 0 ? cmp : bStart - aStart;
      }
      if (sortBy === 'confidence') {
        const confDiff = getVisitMaxConfidence(b) - getVisitMaxConfidence(a);
        return confDiff !== 0 ? confDiff : bStart - aStart;
      }
      if (sortBy === 'duration') {
        const durDiff = getVisitDurationSeconds(b) - getVisitDurationSeconds(a);
        return durDiff !== 0 ? durDiff : bStart - aStart;
      }
      const cmp = getVisitBehaviorSortValue(a).localeCompare(
        getVisitBehaviorSortValue(b),
        i18n.language,
      );
      return cmp !== 0 ? cmp : bStart - aStart;
    });
    return sorted;
  }, [
    selectedBySpeciesVisits,
    birdProfileFilterId,
    birdProfilesById,
    behaviorFilter,
    sortBy,
    i18n.language,
  ]);

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
          triggerSource,
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

  return (
    <>
      {isReviewMode ? (
        <UnknownsPage afterTitleSlot={<RecordingsModeSwitcher />} />
      ) : (
        <>
          <PageHelp {...timelineHelpConfig} />
          <RecordingsModeSwitcher />
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
          {systemMetricsLive ? (
            <Stack
              direction="row"
              spacing={1}
              useFlexGap
              flexWrap="wrap"
              sx={{ mb: 2 }}
            >
              <Chip
                size="small"
                label={t('timeline.runtimeCpu', {
                  value: Math.round(systemMetricsLive.cpu.percent),
                })}
              />
              <Chip
                size="small"
                label={t('timeline.runtimeMemory', {
                  value: Math.round(systemMetricsLive.memory.percent),
                })}
              />
              {systemMetricsLive.gpu_percent != null ? (
                <Chip
                  size="small"
                  label={t('timeline.runtimeGpu', {
                    value: Math.round(systemMetricsLive.gpu_percent),
                  })}
                />
              ) : null}
              <Chip
                size="small"
                variant="outlined"
                label={t('timeline.runtimeEncoding', {
                  value: systemMetricsLive.encoding || 'auto',
                })}
              />
            </Stack>
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
                  disabled={jumpPending}
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
                  disabled={jumpPending || !selectedDate.isBefore(observerToday, 'day')}
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
              {canEdit && (
                <IconButton
                  onClick={(e) => setExportAnchor(e.currentTarget)}
                  disabled={exporting}
                  aria-label={t('timeline.export')}
                  data-testid="timeline-export-menu-trigger"
                >
                  <DownloadIcon />
                </IconButton>
              )}
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
          <Stack
            direction={{ xs: 'column', md: 'row' }}
            spacing={2}
            sx={{ mb: 3 }}
          >
            <Stack
              direction="row"
              spacing={0.5}
              alignItems="flex-start"
              sx={{ minWidth: { xs: '100%', md: 320 } }}
            >
              <BirdProfileFilterAutocomplete
                value={birdProfileFilterId}
                onChange={updateBirdProfileFilter}
                sx={{ flex: 1, minWidth: 0 }}
              />
              {canEdit ? (
                <Tooltip title={t('birdProfiles.manageButton')}>
                  <IconButton
                    size="small"
                    aria-label={t('birdProfiles.manageButton')}
                    data-testid="bird-profiles-catalog-open"
                    onClick={() => setBirdCatalogOpen(true)}
                    sx={{ mt: 0.5 }}
                  >
                    <FormatListBulletedIcon fontSize="small" />
                  </IconButton>
                </Tooltip>
              ) : null}
            </Stack>
            <BehaviorFilterSelect
              value={behaviorFilter}
              onChange={updateBehaviorFilter}
              sx={{ minWidth: { xs: '100%', md: 240 } }}
            />
            <FormControl size="small" sx={{ minWidth: { xs: '100%', md: 220 } }}>
              <InputLabel id="timeline-trigger-source-label">
                {t('timeline.triggerSource')}
              </InputLabel>
              <Select
                labelId="timeline-trigger-source-label"
                value={triggerSource}
                label={t('timeline.triggerSource')}
                onChange={(event) =>
                  setTriggerSource(event.target.value as TimelineTriggerSource)
                }
              >
                {triggerOptions.map((option) => (
                  <MenuItem key={option.value} value={option.value}>
                    {option.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <FormControl size="small" sx={{ minWidth: { xs: '100%', md: 220 } }}>
              <InputLabel id="timeline-sort-by-label">
                {t('timeline.sortBy')}
              </InputLabel>
              <Select
                labelId="timeline-sort-by-label"
                value={sortBy}
                label={t('timeline.sortBy')}
                onChange={(event) =>
                  setSortBy(event.target.value as TimelineSortBy)
                }
              >
                <MenuItem value="date_desc">
                  {t('timeline.sortDateDesc')}
                </MenuItem>
                <MenuItem value="date_asc">{t('timeline.sortDateAsc')}</MenuItem>
                <MenuItem value="species">{t('timeline.sortSpecies')}</MenuItem>
                <MenuItem value="nickname">
                  {t('timeline.sortNickname')}
                </MenuItem>
                <MenuItem value="confidence">
                  {t('timeline.sortConfidence')}
                </MenuItem>
                <MenuItem value="duration">
                  {t('timeline.sortDuration')}
                </MenuItem>
                <MenuItem value="behavior">
                  {t('timeline.sortBehavior')}
                </MenuItem>
              </Select>
            </FormControl>
          </Stack>

          <TimelineStats visits={visits ?? []} />
          <Divider sx={{ marginBottom: 4 }} />
          <Timeline visits={filteredVisits ?? []} />
        </>
      )}
      <BirdProfilesCatalogDialog
        open={birdCatalogOpen}
        onClose={() => setBirdCatalogOpen(false)}
        onDeleted={(profileId) => {
          if (birdProfileFilterId === profileId) {
            updateBirdProfileFilter(null);
          }
        }}
      />
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
