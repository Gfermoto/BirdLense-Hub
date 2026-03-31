import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  LinearProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import { fetchCatalogCoverageMetrics, fetchSpeciesDataQuality } from '../../api/api';

export function SpeciesDataQualityCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ['species-data-quality'],
    queryFn: fetchSpeciesDataQuality,
    staleTime: 60_000,
  });
  const { data: coverage } = useQuery({
    queryKey: ['catalog-coverage-metrics'],
    queryFn: fetchCatalogCoverageMetrics,
    staleTime: 60_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) {
    return <Alert severity="warning">{t('system.speciesDataQualityLoadError')}</Alert>;
  }

  const dupeCount: number = data.duplicate_name_group_count ?? 0;
  const isClean = dupeCount === 0;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t('system.speciesDataQualityTitle')}
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          <Chip
            size="small"
            label={t('system.speciesDataQualityTotal', { n: data.species_total })}
          />
          {isClean ? (
            <Chip
              size="small"
              color="success"
              icon={<CheckCircleIcon />}
              label={t('system.speciesDataQualityClean', 'Catalog clean')}
            />
          ) : (
            <Chip
              size="small"
              color="warning"
              label={t('system.speciesDataQualityDupes', { n: dupeCount })}
            />
          )}
          {coverage && (
            <>
              <Chip
                size="small"
                variant="outlined"
                label={t('system.catalogObservedCount', { n: coverage.observed_species_count })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.catalogDatasetCount', { n: coverage.dataset_species_count })}
              />
              <Chip
                size="small"
                variant="outlined"
                label={t('system.catalogFullEuCount', { n: coverage.full_eu_species_count })}
              />
              <Chip
                size="small"
                color={coverage.tuning_candidate_count > 0 ? 'warning' : 'default'}
                label={t('system.catalogTuningCandidates', { n: coverage.tuning_candidate_count })}
              />
            </>
          )}
        </Box>

        {coverage && coverage.tuning_candidate_count > 0 && (
          <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
            {t('system.catalogTuningHint')}
            {' '}
            {coverage.tuning_candidates.slice(0, 8).map((x) => x.name).join(', ')}
          </Typography>
        )}

        {(data.duplicate_name_groups?.length ?? 0) > 0 && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              {t('system.speciesDataQualityDupesTable')}
            </Typography>
            <TableContainer sx={{ maxHeight: 240 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>{t('system.speciesDataQualityColKey')}</TableCell>
                    <TableCell>{t('system.speciesDataQualityColIds')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.duplicate_name_groups.map((g: { normalized_name: string; species: { id: number; name: string }[] }) => (
                    <TableRow key={g.normalized_name}>
                      <TableCell>{g.normalized_name}</TableCell>
                      <TableCell>
                        {g.species.map((s) => `${s.id}:${s.name}`).join(' · ')}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </CardContent>
    </Card>
  );
}
