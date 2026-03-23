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
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import { useTranslation } from 'react-i18next';
import FilterListIcon from '@mui/icons-material/FilterList';
import { fetchMigrationCalendar } from '../../api/api';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { PageHelp } from '../../components/PageHelp';

/** Intensity 0–1 → opacity for cell background */
const cellOpacity = (count: number, maxInRow: number) =>
  maxInRow > 0 ? 0.15 + 0.65 * (count / maxInRow) : 0;

const currentYear = new Date().getFullYear();
const YEAR_OPTIONS = Array.from({ length: 20 }, (_, i) => currentYear - 10 + i);

export const MigrationCalendar = () => {
  const { t } = useTranslation();
  const [startYear, setStartYear] = useState<number | ''>('');
  const [endYear, setEndYear] = useState<number | ''>('');

  const params = useMemo(() => {
    const s = startYear === '' ? undefined : startYear;
    const e = endYear === '' ? undefined : endYear;
    if (s === undefined && e === undefined) return undefined;
    return { start_year: s ?? undefined, end_year: e ?? undefined };
  }, [startYear, endYear]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['migration-calendar', params],
    queryFn: () => fetchMigrationCalendar(params),
  });

  const checklistYear = endYear === '' ? startYear : endYear;
  const { data: checklistData } = useQuery({
    queryKey: ['migration-calendar-checklist', checklistYear],
    queryFn: () =>
      fetchMigrationCalendar({
        start_year: typeof checklistYear === 'number' ? checklistYear : currentYear,
        end_year: typeof checklistYear === 'number' ? checklistYear : currentYear,
      }),
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
  const yearlySpecies = checklistData?.species ?? [];

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
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 2, flexWrap: 'wrap' }}>
        <FilterListIcon fontSize="small" color="action" />
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
      <Paper sx={{ p: 2, mb: 2 }}>
        <Box
          sx={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            mb: 1.5,
            gap: 1,
            flexWrap: 'wrap',
          }}
        >
          <Typography variant="h6">{t('migrationCalendar.yearlyChecklistTitle')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('migrationCalendar.usesFilterYearHint')}
          </Typography>
        </Box>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1.5 }}>
          {t('migrationCalendar.yearlyChecklistSummary', {
            seen: yearlySpecies.length,
            year: typeof checklistYear === 'number' ? checklistYear : currentYear,
          })}
        </Typography>
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
            gap: 0.5,
            maxHeight: 320,
            overflowY: 'auto',
          }}
        >
          {yearlySpecies.map((s) => (
            <FormControlLabel
              key={s.id}
              control={<Checkbox checked disabled size="small" />}
              label={`${s.name} (${s.total})`}
              sx={{ m: 0 }}
            />
          ))}
          {yearlySpecies.length === 0 && (
            <Typography variant="body2" color="text.secondary">
              {t('migrationCalendar.noChecklistData')}
            </Typography>
          )}
        </Box>
      </Paper>
      <TableContainer component={Paper} sx={{ overflowX: 'auto' }}>
        <Table size="small" stickyHeader>
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
    </Box>
  );
};
