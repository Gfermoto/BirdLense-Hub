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
import { fetchClassifierDatasetAlignment } from '../../api/api';

export function ClassifierDatasetAlignmentCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ['classifier-dataset-alignment'],
    queryFn: fetchClassifierDatasetAlignment,
    staleTime: 120_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) {
    return (
      <Alert severity="warning">{t('system.classifierAlignmentLoadError')}</Alert>
    );
  }

  const aligned = Boolean(data.catalog_classifier_dataset_aligned);
  const canCompare = data.classifier_readable;

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1 }}>
          {t('system.classifierAlignmentTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.classifierAlignmentHint')}
        </Typography>

        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {data.classifier_weights_path} → {data.classifier_weights_resolved}
        </Typography>

        {!canCompare && (
          <Alert severity="info" sx={{ mb: 2 }}>
            {data.classifier_error || t('system.classifierAlignmentNoWeights')}
          </Alert>
        )}

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          <Chip
            size="small"
            label={t('system.classifierAlignmentClassCount', { n: data.classifier_class_count })}
          />
          <Chip
            size="small"
            label={t('system.classifierAlignmentDatasetFolders', { n: data.dataset_folder_count })}
          />
          <Chip
            size="small"
            label={t('system.classifierAlignmentVideoSpecies', { n: data.species_with_video_detections })}
          />
          {canCompare && (
            <Chip
              size="small"
              color={aligned ? 'success' : 'warning'}
              label={
                aligned
                  ? t('system.classifierAlignmentStatusOk')
                  : t('system.classifierAlignmentStatusDrift')
              }
            />
          )}
        </Box>

        {canCompare && !aligned && (
          <>
            <Divider sx={{ my: 2 }} />
            <Typography variant="subtitle2" sx={{ mb: 1 }}>
              {t('system.classifierAlignmentTableModelNotCatalog')}
            </Typography>
            <TableContainer sx={{ maxHeight: 200, mb: 2 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>{t('system.classifierAlignmentColLabel')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.in_classifier_not_in_catalog.length === 0 ? (
                    <TableRow>
                      <TableCell>—</TableCell>
                    </TableRow>
                  ) : (
                    data.in_classifier_not_in_catalog.map((name) => (
                      <TableRow key={name}>
                        <TableCell>{name}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Typography variant="caption" color="text.secondary" display="block">
              {t('system.classifierAlignmentCountTotal', {
                shown: data.in_classifier_not_in_catalog.length,
                total: data.in_classifier_not_in_catalog_count,
              })}
            </Typography>

            <Typography variant="subtitle2" sx={{ mb: 1, mt: 2 }}>
              {t('system.classifierAlignmentTableCatalogNotModel')}
            </Typography>
            <TableContainer sx={{ maxHeight: 200, mb: 2 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>id</TableCell>
                    <TableCell>{t('system.speciesDataQualityColName')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.in_catalog_not_in_classifier.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={2}>—</TableCell>
                    </TableRow>
                  ) : (
                    data.in_catalog_not_in_classifier.map((row) => (
                      <TableRow key={row.id}>
                        <TableCell>{row.id}</TableCell>
                        <TableCell>{row.name}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <Typography variant="caption" color="text.secondary" display="block">
              {t('system.classifierAlignmentCountTotal', {
                shown: data.in_catalog_not_in_classifier.length,
                total: data.in_catalog_not_in_classifier_count,
              })}
            </Typography>

            <Typography variant="subtitle2" sx={{ mb: 1, mt: 2 }}>
              {t('system.classifierAlignmentOrphanFolders')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t('system.classifierAlignmentOrphanFoldersHint', {
                n: data.dataset_folders_without_catalog_match_count,
              })}
            </Typography>
            {data.dataset_folders_without_catalog_match.length > 0 && (
              <Typography variant="body2" component="pre" sx={{ fontFamily: 'inherit', whiteSpace: 'pre-wrap' }}>
                {data.dataset_folders_without_catalog_match.join(', ')}
              </Typography>
            )}

            <Typography variant="subtitle2" sx={{ mb: 1, mt: 2 }}>
              {t('system.classifierAlignmentFolderNotInModel')}
            </Typography>
            <TableContainer sx={{ maxHeight: 180 }}>
              <Table size="small" stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>{t('system.classifierAlignmentColFolder')}</TableCell>
                    <TableCell>{t('system.speciesDataQualityColName')}</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {data.dataset_folders_species_not_in_classifier.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={2}>—</TableCell>
                    </TableRow>
                  ) : (
                    data.dataset_folders_species_not_in_classifier.map((row) => (
                      <TableRow key={`${row.folder}-${row.species_id}`}>
                        <TableCell>{row.folder}</TableCell>
                        <TableCell>{row.species_name}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </TableContainer>
          </>
        )}
      </CardContent>
    </Card>
  );
}
