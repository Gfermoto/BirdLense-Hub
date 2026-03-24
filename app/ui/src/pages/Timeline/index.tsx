import { useState, useEffect } from 'react';
import { useSearchParams, Link, useNavigate } from 'react-router-dom';
import { Timeline } from './Timeline';
import { TimelineStats } from './TimelineStats';
import { SpeciesVisit, Species } from '../../types';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import CircularProgress from '@mui/material/CircularProgress';
import Divider from '@mui/material/Divider';
import Menu from '@mui/material/Menu';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import Button from '@mui/material/Button';
import Alert from '@mui/material/Alert';
import FolderOpenIcon from '@mui/icons-material/FolderOpen';
import DownloadIcon from '@mui/icons-material/Download';
import { AdapterDayjs } from '@mui/x-date-pickers/AdapterDayjs';
import { LocalizationProvider } from '@mui/x-date-pickers/LocalizationProvider';
import { DatePicker } from '@mui/x-date-pickers/DatePicker';
import dayjs, { Dayjs } from 'dayjs';
import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import { fetchTimeline, exportTimeline, exportDataset, fetchUnknowns } from '../../api/api';
import OutlinedInput from '@mui/material/OutlinedInput';
import Checkbox from '@mui/material/Checkbox';
import ListItemText from '@mui/material/ListItemText';
import { PageHelp } from '../../components/PageHelp';
import { timelineHelpConfig } from '../../page-help-config';
import { getTimeRange, type TimeOfDay } from '../../utils/timeUtils';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import Chip from '@mui/material/Chip';
import Badge from '@mui/material/Badge';
import { UnknownsPage } from '../Unknowns';

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
  return visits?.filter((visit) =>
    selectedSpeciesIds.length === 0 || selectedSpeciesIds.includes(visit.species.id),
  );
}

export function TimelinePage() {
  const { t } = useTranslation();
  const { canEdit } = useProtectedArea();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const isReviewMode = searchParams.get('review') === '1';
  const [selectedSpeciesIds, setSelectedSpeciesIds] = useState<number[]>([]);
  const [timeOfDay, setTimeOfDay] = useState<TimeOfDay>('all');
  const [exportAnchor, setExportAnchor] = useState<null | HTMLElement>(null);
  const [exporting, setExporting] = useState(false);
  const [selectedDate, setSelectedDate] = useState<Dayjs | null>(() => {
    const paramDate = searchParams.get('date');
    return paramDate ? dayjs(paramDate).startOf('date') : dayjs().startOf('date');
  });

  const {
    data: visits,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ['speciesVisits', selectedDate?.format('YYYY-MM-DD'), timeOfDay],
    queryFn: () => {
      if (!selectedDate) return [];
      const { start, end } = getTimeRange(selectedDate, timeOfDay);
      return fetchTimeline(start, end);
    },
    enabled: !!selectedDate && !isReviewMode,
  });

  const { data: unknownsCount = 0 } = useQuery({
    queryKey: ['unknowns-count', selectedDate?.format('YYYY-MM-DD'), timeOfDay],
    queryFn: async () => {
      if (!selectedDate) return 0;
      const { start, end } = getTimeRange(selectedDate, timeOfDay);
      const rows = await fetchUnknowns(start, end, 500);
      return rows.length;
    },
    enabled: !!selectedDate,
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

  const speciesList = useSpeciesList(visits);
  const filteredVisits = useFilteredVisits(visits, selectedSpeciesIds);

  const handleSpeciesChange = (event: { target: { value: any } }) => {
    const value = event.target.value;
    setSelectedSpeciesIds(
      typeof value === 'string'
        ? value.split(',').map(Number)
        : value.map(Number),
    );
  };

  const handleExport = async (format: 'csv' | 'json' | 'ebird') => {
    if (!selectedDate) return;
    setExportAnchor(null);
    setExporting(true);
    try {
      const { start, end } = getTimeRange(selectedDate, timeOfDay);
      await exportTimeline(start, end, format);
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  const handleExportDataset = async () => {
    setExportAnchor(null);
    setExporting(true);
    try {
      await exportDataset();
    } catch (err) {
      console.error('Dataset export failed:', err);
    } finally {
      setExporting(false);
    }
  };

  if (!isReviewMode && isLoading)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  if (!isReviewMode && error)
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">{t('timeline.errorLoad')}</Typography>
        <Button variant="outlined" sx={{ mt: 2 }} onClick={() => refetch()}>
          {t('common.retry')}
        </Button>
      </Box>
    );

  return (
    <>
      <Box display="flex" gap={1} alignItems="center" sx={{ mb: 2 }}>
        <Chip
          color={!isReviewMode ? 'primary' : 'default'}
          variant={!isReviewMode ? 'filled' : 'outlined'}
          label={t('timeline.modeTimeline')}
          aria-pressed={!isReviewMode}
          onClick={() => navigate('/timeline')}
        />
        <Chip
          color={isReviewMode ? 'primary' : 'default'}
          variant={isReviewMode ? 'filled' : 'outlined'}
          aria-pressed={isReviewMode}
          onClick={() => navigate('/timeline?review=1')}
          label={
            <Badge
              badgeContent={unknownsCount}
              color="warning"
              max={500}
              invisible={unknownsCount === 0}
            >
              {t('timeline.modeReview')}
            </Badge>
          }
        />
      </Box>
      {isReviewMode ? (
        <UnknownsPage />
      ) : (
        <>
      <PageHelp {...timelineHelpConfig} />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('timeline.intro')}
      </Typography>
      <Alert severity="info" sx={{ mb: 2 }}>
        {t('timeline.noRecords')}{' '}
        <Button
          component={Link}
          to="/library#recordings"
          size="small"
          startIcon={<FolderOpenIcon />}
          sx={{ verticalAlign: 'baseline' }}
        >
          {t('timeline.scanImport')}
        </Button>
        {' '}{t('timeline.scanHint')}.
      </Alert>
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        sx={{ '& > :not(style)': { m: 1, mb: 4, width: '25ch' } }}
      >
        <LocalizationProvider dateAdapter={AdapterDayjs}>
          <DatePicker
            label={t('timeline.selectDate')}
            value={selectedDate}
            onChange={(newValue) => setSelectedDate(newValue)}
            maxDate={dayjs()}
          />
        </LocalizationProvider>
        <FormControl sx={{ minWidth: 160 }}>
          <InputLabel id="timeofday-label">{t('timeline.timeOfDay')}</InputLabel>
          <Select
            labelId="timeofday-label"
            value={timeOfDay}
            onChange={(e) => setTimeOfDay(e.target.value as TimeOfDay)}
            label={t('timeline.timeOfDay')}
          >
            <MenuItem value="all">{t('timeline.timeAllDay')}</MenuItem>
            <MenuItem value="night">{t('timeline.timeNight')}</MenuItem>
            <MenuItem value="morning">{t('timeline.timeMorning')}</MenuItem>
            <MenuItem value="day">{t('timeline.timeDay')}</MenuItem>
            <MenuItem value="afternoon">{t('timeline.timeAfternoon')}</MenuItem>
            <MenuItem value="evening">{t('timeline.timeEvening')}</MenuItem>
          </Select>
        </FormControl>
        <FormControl>
          <InputLabel id="species-select-label">{t('timeline.species')}</InputLabel>
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
                    .filter((species) => selected.includes(Number(species.id)))
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
        <Tooltip title={!canEdit ? t('common.loginRequiredForExport') : t('timeline.export')}>
          <span>
            <IconButton
              onClick={(e) => setExportAnchor(e.currentTarget)}
              disabled={exporting || !canEdit}
              aria-label={t('timeline.export')}
            >
              <DownloadIcon />
            </IconButton>
          </span>
        </Tooltip>
        <Menu
          anchorEl={exportAnchor}
          open={!!exportAnchor}
          onClose={() => setExportAnchor(null)}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'right' }}
          transformOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          <MenuItem onClick={() => handleExport('csv')}>{t('timeline.exportCsv')}</MenuItem>
          <MenuItem onClick={() => handleExport('json')}>{t('timeline.exportJson')}</MenuItem>
          <MenuItem onClick={() => handleExport('ebird')}>{t('timeline.exportEbird')}</MenuItem>
          <MenuItem onClick={() => handleExportDataset()}>{t('storage.exportDataset')}</MenuItem>
        </Menu>
      </Box>

      <TimelineStats visits={filteredVisits ?? []} />
      <Divider sx={{ marginBottom: 4 }} />
      <Timeline visits={filteredVisits ?? []} />
        </>
      )}
    </>
  );
}

export default TimelinePage;
