import React, { useState, useMemo } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Link from '@mui/material/Link';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import Button from '@mui/material/Button';
import { useTranslation } from 'react-i18next';
import FilterListIcon from '@mui/icons-material/FilterList';
import { fetchMigrationCalendar } from '../../api/migrationCalendar';
import { fetchRegionComparison } from '../../api/weatherRegion';
import { queryKeys } from '../../api/queryKeys';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { PageHelp } from '../../components/PageHelp';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import dayjs from 'dayjs';
import { visuallyHidden } from '@mui/utils';

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 20 }, (_, i) => currentYear - 10 + i);

type PeriodMode = 'years' | 'dates';

export const MigrationCalendar = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.migrationCalendar'));
  const [periodMode, setPeriodMode] = useState<PeriodMode>('years');
  const [startYear, setStartYear] = useState<number | ''>('');
  const [endYear, setEndYear] = useState<number | ''>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [catalogMode, setCatalogMode] = useState<'observed' | 'all'>('observed');

  const handlePeriodMode = (
    _: React.MouseEvent<HTMLElement>,
    value: PeriodMode | null,
  ) => {
    if (value === null) return;
    setPeriodMode(value);
    if (value === 'years') {
      setStartDate('');
      setEndDate('');
    } else {
      setStartYear('');
      setEndYear('');
    }
  };

  const params = useMemo(() => {
    let base: {
      start_year?: number;
      end_year?: number;
      start_date?: string;
      end_date?: string;
      catalog?: 'observed' | 'all';
    } = {
      catalog: catalogMode,
    };
    if (periodMode === 'years') {
      const s = startYear === '' ? undefined : startYear;
      const e = endYear === '' ? undefined : endYear;
      if (s === undefined && e === undefined) {
        return base;
      }
      base = {
        ...base,
        start_year: s ?? undefined,
        end_year: e ?? undefined,
      };
      return base;
    }
    const sd = startDate || undefined;
    const ed = endDate || undefined;
    if (!sd && !ed) {
      return base;
    }
    return {
      ...base,
      start_date: sd,
      end_date: ed,
    };
  }, [periodMode, startYear, endYear, startDate, endDate, catalogMode]);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: queryKeys.calendar.migrationData(params),
    queryFn: () => fetchMigrationCalendar(params),
  });

  const { data: regionComparison } = useQuery({
    queryKey: queryKeys.calendar.regionComparison,
    queryFn: () => fetchRegionComparison(),
    staleTime: 1000 * 60 * 10, // 10 min
    retry: false,
  });

  if (isLoading) {
    return <PageLoadingState label={t('common.loading')} />;
  }

  if (error || !data) {
    return (
      <PageMessageState
        title={t('migrationCalendar.title')}
        message={t('migrationCalendar.errorLoad')}
        severity="error"
        action={
          <Button variant="outlined" onClick={() => refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }

  const { species, month_labels } = data;

  return (
    <Box sx={{ py: 2 }}>
      <PageHelp configKey="migrationCalendar" />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('migrationCalendar.description')}
      </Typography>
      <Box
        component="section"
        aria-labelledby="migration-filters-heading"
        sx={{ display: 'flex', flexDirection: 'column', gap: 1.5, mb: 2 }}
      >
        <Typography
          id="migration-filters-heading"
          component="h2"
          sx={visuallyHidden}
        >
          {t('migrationCalendar.filterSectionTitle')}
        </Typography>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 2,
          }}
        >
          <FilterListIcon fontSize="small" color="action" aria-hidden />
          <ToggleButtonGroup
            value={periodMode}
            exclusive
            size="small"
            color="primary"
            onChange={handlePeriodMode}
            aria-label={t('migrationCalendar.periodModeAria')}
          >
            <ToggleButton
              value="years"
              title={t('migrationCalendar.periodModeYearsTooltip')}
            >
              {t('migrationCalendar.periodModeYears')}
            </ToggleButton>
            <ToggleButton
              value="dates"
              title={t('migrationCalendar.periodModeDatesTooltip')}
            >
              {t('migrationCalendar.periodModeDates')}
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
        {periodMode === 'years' ? (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <TextField
              select
              size="small"
              label={t('migrationCalendar.startYear')}
              value={startYear}
              onChange={(e) =>
                setStartYear(
                  e.target.value === '' ? '' : Number(e.target.value),
                )
              }
              sx={{ minWidth: 100 }}
            >
              <MenuItem value="">{t('migrationCalendar.allYears')}</MenuItem>
              {YEAR_OPTIONS.map((y) => (
                <MenuItem key={y} value={y}>
                  {y}
                </MenuItem>
              ))}
            </TextField>
            <TextField
              select
              size="small"
              label={t('migrationCalendar.endYear')}
              value={endYear}
              onChange={(e) =>
                setEndYear(e.target.value === '' ? '' : Number(e.target.value))
              }
              sx={{ minWidth: 100 }}
            >
              <MenuItem value="">{t('migrationCalendar.allYears')}</MenuItem>
              {YEAR_OPTIONS.map((y) => (
                <MenuItem key={y} value={y}>
                  {y}
                </MenuItem>
              ))}
            </TextField>
          </Box>
        ) : (
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
              flexWrap: 'wrap',
            }}
          >
            <TextField
              type="date"
              size="small"
              label={t('migrationCalendar.startDate')}
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              inputProps={{ max: endDate || dayjs().format('YYYY-MM-DD') }}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 170 }}
            />
            <TextField
              type="date"
              size="small"
              label={t('migrationCalendar.endDate')}
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              inputProps={{
                min: startDate || undefined,
                max: dayjs().format('YYYY-MM-DD'),
              }}
              InputLabelProps={{ shrink: true }}
              sx={{ minWidth: 170 }}
            />
          </Box>
        )}
        <Typography variant="caption" color="text.secondary" display="block">
          {t('migrationCalendar.periodHint')}
        </Typography>
        <Box
          sx={{
            display: 'flex',
            flexWrap: 'wrap',
            alignItems: 'center',
            gap: 2,
            mt: 1,
          }}
        >
          <ToggleButtonGroup
            exclusive
            size="small"
            color="primary"
            value={catalogMode}
            onChange={(_e, value: 'observed' | 'all' | null) => {
              if (value) setCatalogMode(value);
            }}
            aria-label={t('migrationCalendar.catalogLabel')}
          >
            <ToggleButton
              value="observed"
              title={t('migrationCalendar.catalogMenuHintObserved')}
            >
              {t('migrationCalendar.catalogObserved')}
            </ToggleButton>
            <ToggleButton
              value="all"
              title={t('migrationCalendar.catalogMenuHintAll')}
            >
              {t('migrationCalendar.catalogAll')}
            </ToggleButton>
          </ToggleButtonGroup>
        </Box>
        <Typography
          variant="caption"
          color="text.secondary"
          display="block"
          sx={{ mt: 0.5 }}
        >
          {t('migrationCalendar.catalogEvidenceHint')}
        </Typography>
      </Box>
      {species.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">
            {catalogMode === 'all'
              ? t('migrationCalendar.noSpeciesInDb')
              : t('migrationCalendar.noObserved')}
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
          <Table size="small" stickyHeader>
            <caption style={visuallyHidden as React.CSSProperties}>
              {t('migrationCalendar.tableCaption')}
            </caption>
            <TableHead>
              <TableRow>
                <TableCell sx={{ fontWeight: 600, minWidth: 180 }}>
                  {t('migrationCalendar.species')}
                </TableCell>
                {month_labels.map((m) => (
                  <TableCell
                    key={m}
                    align="center"
                    sx={{ fontWeight: 600, minWidth: 44 }}
                  >
                    {m}
                  </TableCell>
                ))}
                <TableCell align="right" sx={{ fontWeight: 600 }}>
                  Σ
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {species.map((s) => {
                const maxInRow = Math.max(...s.monthly_counts, 1);
                const hasSpeciesId =
                  Number.isInteger(s.id) && (s.id as number) > 0;
                return (
                  <TableRow key={`${s.id ?? 'noid'}:${s.name}`} hover>
                    <TableCell sx={{ verticalAlign: 'middle' }}>
                      {hasSpeciesId ? (
                        <Link
                          component={RouterLink}
                          to={`/species/${s.id}`}
                          underline="hover"
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1.5,
                            color: 'inherit',
                          }}
                        >
                          <SpeciesIcon
                            speciesName={s.name}
                            imageUrl={s.image_url}
                            size={32}
                          />
                          {s.name}
                        </Link>
                      ) : (
                        <Box
                          sx={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 1.5,
                            color: 'text.secondary',
                          }}
                        >
                          <SpeciesIcon
                            speciesName={s.name}
                            imageUrl={s.image_url}
                            size={32}
                          />
                          {s.name}
                        </Box>
                      )}
                    </TableCell>
                    {s.monthly_counts.map((count, i) => {
                      const intensity = maxInRow > 0 ? count / maxInRow : 0;
                      return (
                        <TableCell
                          key={i}
                          align="center"
                          sx={{
                            minWidth: 44,
                            color:
                              count > 0 ? 'text.primary' : 'text.secondary',
                            borderLeft:
                              count > 0
                                ? `3px solid rgba(16, 185, 129, ${0.45 + 0.55 * intensity})`
                                : '3px solid transparent',
                            bgcolor:
                              count > 0
                                ? `rgba(16, 185, 129, 0.08)`
                                : 'transparent',
                          }}
                        >
                          {count > 0 ? count : '—'}
                        </TableCell>
                      );
                    })}
                    <TableCell align="right" sx={{ fontWeight: 500 }}>
                      {s.total}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <Paper sx={{ p: 2, mt: 2 }}>
        <Typography variant="h6" gutterBottom>
          {t('overview.regionComparison')}
        </Typography>
        {regionComparison?.regionCode && regionComparison.regionTopCount > 0 ? (
          <>
            <Typography variant="body1">
              {t('overview.regionComparisonDesc', {
                userCount: regionComparison.userCount,
                regionTop: regionComparison.regionTopCount,
                matchCount: regionComparison.matchCount,
              })}
            </Typography>
            {regionComparison.matchedSpecies?.length > 0 && (
              <Box sx={{ mt: 1.5 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  {t('overview.regionComparisonMatched')}
                </Typography>
                <Box
                  component="ul"
                  sx={{
                    m: 0,
                    pl: 2.5,
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 0.5,
                    '& li': { display: 'inline' },
                    '& li:not(:last-child)::after': {
                      content: '" · "',
                      color: 'text.secondary',
                    },
                  }}
                >
                  {regionComparison.matchedSpecies.map((name) => (
                    <li key={name}>
                      <Typography
                        component="span"
                        variant="body2"
                        fontWeight={500}
                      >
                        {name}
                      </Typography>
                    </li>
                  ))}
                </Box>
              </Box>
            )}
            {regionComparison.regionTop?.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography
                  variant="subtitle2"
                  color="text.secondary"
                  gutterBottom
                >
                  {t('overview.regionComparisonTopList')}
                </Typography>
                <Box
                  sx={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    gap: 0.75,
                  }}
                >
                  {regionComparison.regionTop.map((name, idx) => (
                    <Typography
                      key={name}
                      component="span"
                      variant="body2"
                      sx={{
                        px: 1,
                        py: 0.25,
                        borderRadius: 1,
                        bgcolor: 'action.hover',
                      }}
                    >
                      {idx + 1}. {name}
                    </Typography>
                  ))}
                </Box>
              </Box>
            )}
            <Typography
              variant="caption"
              color="text.secondary"
              display="block"
              sx={{ mt: 1 }}
            >
              {t('overview.regionComparisonHint', {
                region: regionComparison.regionCode,
              })}
            </Typography>
          </>
        ) : regionComparison?.regionCode ? (
          <Typography variant="body2" color="text.secondary">
            {t('overview.regionComparisonNoData', {
              region: regionComparison.regionCode,
            })}
          </Typography>
        ) : (
          <Typography variant="body2" color="text.secondary">
            {t('overview.regionComparisonConfigure')}
          </Typography>
        )}
      </Paper>
    </Box>
  );
};
