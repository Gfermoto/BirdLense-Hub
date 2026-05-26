import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link as RouterLink } from 'react-router-dom';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardActions from '@mui/material/CardActions';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import Grid from '@mui/material/Grid2';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { resolveImageUrl } from '../../api/api';
import { fetchBirdDirectory } from '../../api/speciesOverviewDetections';
import { queryKeys } from '../../api/queryKeys';
import { PageHeader } from '../../components/PageHeader';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

type CatalogQualityFilter = 'all' | 'no_image' | 'no_description' | 'incomplete';

export function SpeciesDirectoryPage() {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');
  const [qualityFilter, setQualityFilter] = useState<CatalogQualityFilter>('all');
  useDocumentTitle(t('nav.species'));

  const speciesQ = useQuery({
    queryKey: queryKeys.speciesDirectory.list,
    queryFn: fetchBirdDirectory,
    staleTime: 5 * 60 * 1000,
  });

  const filtered = useMemo(() => {
    const normalizeNeedle = (value: string) =>
      value
        .toLowerCase()
        .replace(/[-_]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    const needle = normalizeNeedle(query);
    const rows = speciesQ.data ?? [];
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
          const desc = normalizeNeedle(String(row.description || ''));
          return name.includes(needle) || desc.includes(needle);
        });
    if (qualityFilter === 'all') return bySearch;
    return bySearch.filter((row) => {
      const hasImage = Boolean(String(row.image_url || '').trim());
      const hasDesc = Boolean(String(row.description || '').trim());
      if (qualityFilter === 'no_image') return !hasImage;
      if (qualityFilter === 'no_description') return !hasDesc;
      return !hasImage || !hasDesc;
    });
  }, [query, qualityFilter, speciesQ.data]);

  return (
    <Box display="grid" gap={3} sx={{ pb: 5 }}>
      <PageHeader
        title={t('speciesDirectory.title')}
        description={t('speciesDirectory.description')}
        titleVariant="h3"
      />

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
        <ToggleButton value="no_image">{t('speciesDirectory.filterNoImage')}</ToggleButton>
        <ToggleButton value="no_description">
          {t('speciesDirectory.filterNoDescription')}
        </ToggleButton>
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
                count: speciesQ.data?.length ?? 0,
              })}
              size="small"
              color="primary"
            />
            <Chip
              label={t('speciesDirectory.filteredCount', {
                count: filtered.length,
              })}
              size="small"
              variant="outlined"
            />
          </Stack>

          {filtered.length === 0 ? (
            <Alert severity="info">{t('speciesDirectory.empty')}</Alert>
          ) : (
            <Grid container spacing={2}>
              {filtered.map((species) => (
                <Grid key={species.id} size={{ xs: 12, md: 6, xl: 4 }}>
                  <Card sx={{ height: '100%' }}>
                    <CardContent>
                      <Stack
                        direction="row"
                        spacing={2}
                        alignItems="flex-start"
                      >
                        <Box
                          sx={{
                            width: 56,
                            height: 56,
                            borderRadius: 2,
                            overflow: 'hidden',
                            bgcolor: 'action.hover',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            flexShrink: 0,
                          }}
                        >
                          {species.image_url ? (
                            <Box
                              component="img"
                              src={resolveImageUrl(species.image_url)}
                              alt={species.name}
                              sx={{
                                width: '100%',
                                height: '100%',
                                objectFit: 'cover',
                              }}
                            />
                          ) : (
                            <SpeciesIcon speciesName={species.name} size={34} />
                          )}
                        </Box>
                        <Box sx={{ minWidth: 0, flex: 1 }}>
                          <Typography variant="h6">{species.name}</Typography>
                          <Stack
                            direction="row"
                            flexWrap="wrap"
                            gap={1}
                            sx={{ mt: 1 }}
                          >
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
                            {!species.image_url ? (
                              <Chip
                                size="small"
                                color="warning"
                                variant="outlined"
                                label={t('speciesDirectory.badgeNoImage')}
                              />
                            ) : null}
                            {!species.description ? (
                              <Chip
                                size="small"
                                color="warning"
                                variant="outlined"
                                label={t('speciesDirectory.badgeNoDescription')}
                              />
                            ) : null}
                          </Stack>
                          {species.description ? (
                            <Typography
                              variant="body2"
                              color="text.secondary"
                              sx={{ mt: 1.5 }}
                            >
                              {species.description}
                            </Typography>
                          ) : null}
                        </Box>
                      </Stack>
                    </CardContent>
                    <CardActions>
                      <Button
                        component={RouterLink}
                        to={`/species/${species.id}`}
                        size="small"
                        title={t('speciesDirectory.openSpeciesTooltip')}
                      >
                        {t('speciesDirectory.openSpecies')}
                      </Button>
                      <Button
                        component={RouterLink}
                        to={`/timeline?speciesId=${species.id}`}
                        size="small"
                        color="inherit"
                        title={t('speciesDirectory.openRecordingsTooltip')}
                      >
                        {t('speciesDirectory.openRecordingsForSpecies')}
                      </Button>
                    </CardActions>
                  </Card>
                </Grid>
              ))}
            </Grid>
          )}
        </>
      ) : null}
    </Box>
  );
}

export default SpeciesDirectoryPage;
