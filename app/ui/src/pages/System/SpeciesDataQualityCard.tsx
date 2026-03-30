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
import { fetchSpeciesDataQuality } from '../../api/api';

export function SpeciesDataQualityCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ['species-data-quality'],
    queryFn: fetchSpeciesDataQuality,
    staleTime: 60_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) {
    return <Alert severity="warning">{t('system.speciesDataQualityLoadError')}</Alert>;
  }

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t('system.speciesDataQualityTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.speciesDataQualityHint')}
        </Typography>

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          <Chip
            size="small"
            label={t('system.speciesDataQualityTotal', { n: data.species_total })}
          />
          <Chip
            size="small"
            color={data.suspect_count > 0 ? 'warning' : 'success'}
            label={t('system.speciesDataQualitySuspects', { n: data.suspect_count })}
          />
          <Chip
            size="small"
            color={data.duplicate_name_group_count > 0 ? 'warning' : 'default'}
            label={t('system.speciesDataQualityDupes', { n: data.duplicate_name_group_count })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.speciesDataQualityBlocklist', { n: data.blocklist_entries })}
          />
        </Box>

        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {data.hints?.merge_duplicates_endpoint ? `${data.hints.merge_duplicates_endpoint}` : ''}
        </Typography>

        {data.suspects.length > 0 ? (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              {t('system.speciesDataQualitySuspectTable')}
            </Typography>
            <TableContainer sx={{ maxHeight: 320 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>id</TableCell>
                    <TableCell>{t('system.speciesDataQualityColName')}</TableCell>
                    <TableCell>{t('system.speciesDataQualityColReasons')}</TableCell>
                    <TableCell align="right">{t('system.speciesDataQualityColVisits')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.suspects.map((row) => (
                    <TableRow key={row.id}>
                      <TableCell>{row.id}</TableCell>
                      <TableCell>{row.name}</TableCell>
                      <TableCell>{row.reasons.join(', ')}</TableCell>
                      <TableCell align="right">{row.visit_weight}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        ) : null}

        {data.duplicate_name_groups.length > 0 ? (
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
                  {data.duplicate_name_groups.map((g) => (
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
        ) : null}
      </CardContent>
    </Card>
  );
}
