import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Link from '@mui/material/Link';
import Paper from '@mui/material/Paper';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableContainer from '@mui/material/TableContainer';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { resolveImageUrl } from '../../api/api';
import {
  fetchBirdDirectory,
  type SpeciesCatalogScope,
  type SpeciesDirectoryResponse,
} from '../../api/speciesOverviewDetections';
import { queryKeys } from '../../api/queryKeys';
import { PageHeader } from '../../components/PageHeader';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import type { Species } from '../../types';

type CatalogQualityFilter = 'all' | 'incomplete';

function isDirectoryPayload(
  data: Species[] | SpeciesDirectoryResponse | undefined,
): data is SpeciesDirectoryResponse {
  return Boolean(data && typeof data === 'object' && 'items' in data);
}

export function SpeciesDirectoryPage() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [qualityFilter, setQualityFilter] = useState<CatalogQualityFilter>('all');
  const [scope, setScope] = useState<SpeciesCatalogScope>('allowlist');
  useDocumentTitle(t('nav.species'));

  const speciesQ = useQuery({
    queryKey: [...queryKeys.speciesDirectory.list, scope],
    queryFn: () => fetchBirdDirectory({ scope, meta: true }),
    staleTime: 5 * 60 * 1000,
  });

  const rows = useMemo(() => {
    const data = speciesQ.data;
    if (isDirectoryPayload(data)) return data.items;
    return (data as Species[] | undefined) ?? [];
  }, [speciesQ.data]);

  const meta = isDirectoryPayload(speciesQ.data) ? speciesQ.data.meta : undefined;

  const filtered = useMemo(() => {
    const normalizeNeedle = (value: string) =>
      value
        .toLowerCase()
        .replace(/[-_]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    const needle = normalizeNeedle(query);
    const sorted = [...rows].sort((a, b) => {
      const aCount = Number(a.count ?? 0);
      const bCount = Number(b.count ?? 0);
      if (bCount !== aCount) return bCount - aCount;
      return a.name.localeCompare(b.name);
    });
    const bySearch = !needle
      ? sorted
      : sorted.filter((row) => {
          const name = normalizeNeedle(String(row.name || ''));
          const dbName = normalizeNeedle(String((row as { db_name?: string }).db_name || ''));
          const sci = normalizeNeedle(String((row as { scientific_name?: string }).scientific_name || ''));
          const desc = normalizeNeedle(String(row.description || ''));
          return (
            name.includes(needle) ||
            dbName.includes(needle) ||
            sci.includes(needle) ||
            desc.includes(needle)
          );
        });
    if (qualityFilter === 'all') return bySearch;
    return bySearch.filter((row) => Boolean(row.catalog_card_incomplete));
  }, [query, qualityFilter, rows]);

  return (
    <Box display="grid" gap={3} sx={{ pb: 5 }}>
      <PageHeader
        title={t('speciesDirectory.title')}
        description={t('speciesDirectory.description')}
        titleVariant="h3"
      />

      <Typography variant="body2" color="text.secondary">
        <Link component={RouterLink} to="/species" underline="hover">
          {t('speciesDirectory.backToCatalog')}
        </Link>
      </Typography>

      {meta ? (
        <Alert severity="info" sx={{ '& .MuiAlert-message': { width: '100%' } }}>
          {t('speciesDirectory.scopeHint', {
            engine: meta.classifier_engine ?? '—',
            classCount: meta.classifier_class_count ?? meta.allowlist_total,
            db: meta.db_species_total,
            incomplete: meta.allowlist_incomplete,
          })}
        </Alert>
      ) : null}

      <ToggleButtonGroup
        exclusive
        size="small"
        value={scope}
        onChange={(_e, value: SpeciesCatalogScope | null) => {
          if (value) setScope(value);
        }}
        sx={{ flexWrap: 'wrap' }}
      >
        <ToggleButton value="allowlist">
          {t('speciesDirectory.scopeAllowlist')}
        </ToggleButton>
        <ToggleButton value="observed">
          {t('speciesDirectory.scopeObserved')}
        </ToggleButton>
        <ToggleButton value="all">
          {t('speciesDirectory.scopeAllDb')}
        </ToggleButton>
      </ToggleButtonGroup>

      <ToggleButtonGroup
        exclusive
        size="small"
        value={qualityFilter}
        onChange={(_e, value: CatalogQualityFilter | null) => {
          if (value) setQualityFilter(value);
        }}
        sx={{ flexWrap: 'wrap' }}
      >
        <ToggleButton value="all">{t('speciesDirectory.filterAll')}</ToggleButton>
        <ToggleButton value="incomplete">
          {t('speciesDirectory.filterIncomplete')}
        </ToggleButton>
      </ToggleButtonGroup>

      <TextField
        type="search"
        label={t('speciesDirectory.search')}
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder={t('speciesDirectory.searchPlaceholder')}
        fullWidth
        inputProps={{ role: 'searchbox' }}
      />

      {speciesQ.isLoading ? <LinearProgress /> : null}
      {speciesQ.isError ? (
        <Alert severity="error">{t('speciesDirectory.loadError')}</Alert>
      ) : null}

      {!speciesQ.isLoading && !speciesQ.isError ? (
        <>
          <Stack direction="row" flexWrap="wrap" gap={1}>
            <Chip
              label={t('speciesDirectory.totalCount', {
                count: rows.length,
              })}
              size="small"
              color="primary"
            />
            {scope === 'allowlist' && meta ? (
              <Chip
                label={t('speciesDirectory.allowlistModelCount', {
                  count: meta.allowlist_total,
                })}
                size="small"
                variant="outlined"
              />
            ) : null}
            <Chip
              label={t('speciesDirectory.filteredCount', {
                count: filtered.length,
              })}
              size="small"
              variant="outlined"
            />
            {qualityFilter === 'incomplete' && meta && scope === 'allowlist' ? (
              <Chip
                label={t('speciesDirectory.incompleteAllowlistCount', {
                  count: meta.allowlist_incomplete,
                })}
                size="small"
                color="warning"
                variant="outlined"
              />
            ) : null}
          </Stack>

          {filtered.length === 0 ? (
            <Alert severity="info">{t('speciesDirectory.empty')}</Alert>
          ) : (
            <TableContainer component={Paper} variant="outlined">
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell width={52} />
                    <TableCell>{t('speciesDirectory.colSpecies')}</TableCell>
                    <TableCell>{t('speciesDirectory.colStatus')}</TableCell>
                    <TableCell align="right">
                      {t('speciesDirectory.colActions')}
                    </TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filtered.map((species) => (
                    <TableRow key={species.id} hover>
                      <TableCell>
                        <Box
                          sx={{
                            width: 40,
                            height: 40,
                            borderRadius: 1,
                            overflow: 'hidden',
                            bgcolor: 'action.hover',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                          }}
                        >
                          {species.image_url ? (
                            <Box
                              component="img"
                              src={resolveImageUrl(species.image_url)}
                              alt=""
                              sx={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover',
                              }}
                            />
                          ) : (
                            <SpeciesIcon speciesName={species.name} size={28} />
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={600}>
                          {species.name}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Stack direction="row" flexWrap="wrap" gap={0.5}>
                          <Chip
                            size="small"
                            color={species.active ? 'success' : 'default'}
                            label={
                              species.active
                                ? t('speciesDirectory.activeNow')
                                : t('speciesDirectory.inHistory')
                            }
                          />
                          {typeof species.count === 'number' ? (
                            <Chip
                              size="small"
                              variant="outlined"
                              label={t('speciesDirectory.recordsCount', {
                                count: species.count,
                              })}
                            />
                          ) : null}
                          {species.catalog_card_incomplete ? (
                            <Chip
                              size="small"
                              color="warning"
                              variant="outlined"
                              label={t('speciesDirectory.badgeIncomplete')}
                            />
                          ) : null}
                        </Stack>
                      </TableCell>
                      <TableCell align="right">
                        <Stack
                          direction="row"
                          spacing={1}
                          justifyContent="flex-end"
                          flexWrap="wrap"
                        >
                          <Button
                            component={RouterLink}
                            to={`/species/${species.id}`}
                            size="small"
                          >
                            {t('speciesDirectory.openSpecies')}
                          </Button>
                          <Button
                            component={RouterLink}
                            to={`/timeline?speciesId=${species.id}`}
                            size="small"
                            color="inherit"
                          >
                            {t('speciesDirectory.openRecordingsForSpecies')}
                          </Button>
                        </Stack>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          )}
        </>
      ) : null}
    </Box>
  );
}

export default SpeciesDirectoryPage;
