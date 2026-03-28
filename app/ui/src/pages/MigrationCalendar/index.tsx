import React, { useState, useMemo } from 'react';
import { Link as RouterLink } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import Box from '@mui/material/Box';
import Paper from '@mui/material/Paper';
import Typography from '@mui/material/Typography';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Link from '@mui/material/Link';
import CircularProgress from '@mui/material/CircularProgress';
import TextField from '@mui/material/TextField';
import MenuItem from '@mui/material/MenuItem';
import { useTranslation } from 'react-i18next';
import FilterListIcon from '@mui/icons-material/FilterList';
import { fetchMigrationCalendar, fetchRegionComparison } from '../../api/api';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { PageHelp } from '../../components/PageHelp';
import dayjs from 'dayjs';
import { visuallyHidden } from '@mui/utils';

/** Intensity 0–1 → opacity for cell background */
const cellOpacity = (count: number, maxInRow: number) =>
  maxInRow > 0 ? 0.15 + 0.65 * (count / maxInRow) : 0;

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 20 }, (_, i) => currentYear - 10 + i);

export const MigrationCalendar = () => {
  const { t } = useTranslation();
  const [startYear, setStartYear] = useState<number | ''>('');
  const [endYear, setEndYear] = useState<number | ''>('');
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');

  const params = useMemo(() => {
    const s = startYear === '' ? undefined : startYear;
    const e = endYear === '' ? undefined : endYear;
    const sd = startDate || undefined;
    const ed = endDate || undefined;
    if (s === undefined && e === undefined && !sd && !ed) return undefined;
    return {
      start_year: s ?? undefined,
      end_year: e ?? undefined,
      start_date: sd,
      end_date: ed,
    };
  }, [startYear, endYear, startDate, endDate]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['migration-calendar', params],
    queryFn: () => fetchMigrationCalendar(params),
  });

  const { data: regionComparison } = useQuery({
    queryKey: ['region-comparison'],
    queryFn: () => fetchRegionComparison(),
    staleTime: 1000 * 60 * 10, // 10 min
    retry: false,
  });

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', py: 8 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error || !data) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography color="error">{t('migrationCalendar.errorLoad')}</Typography>
      </Box>
    );
  }

  const { species, month_labels } = data;

  if (species.length === 0) {
    return (
      <Box sx={{ py: 4 }}>
        <PageHelp configKey="migrationCalendar" />
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography color="text.secondary">{t('migrationCalendar.noData')}</Typography>
        </Paper>
      </Box>
    );
  }

  return (
    <Box sx={{ py: 2 }}>
      <PageHelp configKey="migrationCalendar" />
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('migrationCalendar.description')}
      </Typography>
      <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1.5 }}>
        {t('migrationCalendar.periodHint')}
      </Typography>
      <Box
        component="section"
        aria-labelledby="migration-filters-heading"
        sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}
      >
        <Typography id="migration-filters-heading" component="h2" sx={visuallyHidden}>
          {t('migrationCalendar.filterSectionTitle')}
        </Typography>
        <FilterListIcon fontSize="small" color="action" aria-hidden />
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
        <TextField
          select
          size="small"
          label={t('migrationCalendar.startYear')}
          value={startYear}
          onChange={(e) => setStartYear(e.target.value === '' ? '' : Number(e.target.value))}
          sx={{ minWidth: 100 }}
        >
          <MenuItem value="">{t('migrationCalendar.allYears')}</MenuItem>
          {YEAR_OPTIONS.map((y) => (
            <MenuItem key={y} value={y}>{y}</MenuItem>
          ))}
        </TextField>
        <TextField
          select
          size="small"
          label={t('migrationCalendar.endYear')}
          value={endYear}
          onChange={(e) => setEndYear(e.target.value === '' ? '' : Number(e.target.value))}
          sx={{ minWidth: 100 }}
        >
          <MenuItem value="">{t('migrationCalendar.allYears')}</MenuItem>
          {YEAR_OPTIONS.map((y) => (
            <MenuItem key={y} value={y}>{y}</MenuItem>
          ))}
        </TextField>
      </Box>
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
                <TableCell key={m} align="center" sx={{ fontWeight: 600, minWidth: 44 }}>
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
              return (
                <TableRow key={s.id} hover>
                  <TableCell sx={{ verticalAlign: 'middle' }}>
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
                      <SpeciesIcon speciesName={s.name} imageUrl={s.image_url} size={32} />
                      {s.name}
                    </Link>
                  </TableCell>
                  {s.monthly_counts.map((count, i) => (
                    <TableCell
                      key={i}
                      align="center"
                      sx={{
                        bgcolor: `rgba(16, 185, 129, ${cellOpacity(count, maxInRow)})`,
                        minWidth: 44,
                      }}
                    >
                      {count > 0 ? count : '—'}
                    </TableCell>
                  ))}
                  <TableCell align="right" sx={{ fontWeight: 500 }}>
                    {s.total}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </TableContainer>

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
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
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
                    '& li:not(:last-child)::after': { content: '" · "', color: 'text.secondary' },
                  }}
                >
                  {regionComparison.matchedSpecies.map((name) => (
                    <li key={name}>
                      <Typography component="span" variant="body2" fontWeight={500}>
                        {name}
                      </Typography>
                    </li>
                  ))}
                </Box>
              </Box>
            )}
            {regionComparison.regionTop?.length > 0 && (
              <Box sx={{ mt: 2 }}>
                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
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
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              {t('overview.regionComparisonHint', { region: regionComparison.regionCode })}
            </Typography>
          </>
        ) : regionComparison?.regionCode ? (
          <Typography variant="body2" color="text.secondary">
            {t('overview.regionComparisonNoData', { region: regionComparison.regionCode })}
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
