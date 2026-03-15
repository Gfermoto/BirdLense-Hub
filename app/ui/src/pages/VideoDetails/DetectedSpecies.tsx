import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import CardMedia from '@mui/material/CardMedia';
import CardActions from '@mui/material/CardActions';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import Share from '@mui/icons-material/Share';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import { Link } from 'react-router-dom';
import { VideoSpecies } from '../../types';
import { labelToUniqueHexColor } from '../../util';
import { SpeciesIcon } from '../../components/SpeciesIcon';
import { resolveImageUrl, downloadDetectionCropForINaturalist } from '../../api/api';

interface GroupedSpecies {
  species_id: number;
  species_name: string;
  image_url?: string;
  detections: VideoSpecies[];
  confidenceRange: string;
  totalDuration: number;
}

const INaturalistButton = ({
  detectionId,
  speciesName,
}: {
  detectionId: number;
  speciesName: string;
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const handleClick = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      await downloadDetectionCropForINaturalist(detectionId, speciesName);
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : String(err));
      console.error('iNaturalist export failed:', err);
    } finally {
      setLoading(false);
    }
  };
  return (
    <>
      <Tooltip title={t('common.iNaturalist')}>
        <span>
          <IconButton size="small" onClick={handleClick} disabled={loading} aria-label={t('common.iNaturalist')}>
            <Share fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Snackbar
        open={!!errorMsg}
        autoHideDuration={6000}
        onClose={() => setErrorMsg(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert severity="error" onClose={() => setErrorMsg(null)}>
          {errorMsg}
        </Alert>
      </Snackbar>
    </>
  );
};

interface DetectedSpeciesProps {
  species: VideoSpecies[];
}

export const DetectedSpecies: React.FC<DetectedSpeciesProps> = ({
  species,
}) => {
  const { t } = useTranslation();
  // Group species by species_id and calculate stats
  const groupedSpecies = species
    .filter((s) => s.source === 'video')
    .reduce((groups: GroupedSpecies[], sp) => {
      let group = groups.find((g) => g.species_id === sp.species_id);
      if (!group) {
        group = {
          species_id: sp.species_id,
          species_name: sp.species_name,
          image_url: sp.image_url,
          detections: [],
          confidenceRange: '',
          totalDuration: 0,
        };
        groups.push(group);
      }
      group.detections.push(sp);
      group.totalDuration += sp.end_time - sp.start_time;
      return groups;
    }, []);

  // Calculate confidence range for each group
  groupedSpecies.forEach((group) => {
    const confidences = group.detections.map((d) => d.confidence * 100);
    const min = Math.min(...confidences).toFixed(0);
    const max = Math.max(...confidences).toFixed(0);
    group.confidenceRange = min === max ? `${min}%` : `${min}% - ${max}%`;
  });

  if (groupedSpecies.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mt: 3 }}>
      <Typography variant="h6" gutterBottom>
        {t('video.speciesInVideo')}
      </Typography>
      <Grid container spacing={2}>
        {groupedSpecies.map((group) => (
          <Grid size={{ xs: 12, sm: 6, md: 4 }} key={group.species_id}>
            <Card
              sx={{
                height: '100%',
                display: 'flex',
                flexDirection: 'column',
                border: `2px solid ${labelToUniqueHexColor(group.species_name)}`,
              }}
            >
              <Box
                sx={{
                  aspectRatio: '16/10',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  bgcolor: 'action.hover',
                  overflow: 'hidden',
                }}
              >
                {group.image_url ? (
                  <CardMedia
                    component="img"
                    alt={group.species_name}
                    image={resolveImageUrl(group.image_url)}
                    sx={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      objectPosition: 'center top',
                    }}
                  />
                ) : (
                  <SpeciesIcon speciesName={group.species_name} size={64} />
                )}
              </Box>
              <CardContent sx={{ py: 1.5 }}>
                <Typography variant="subtitle1" noWrap>
                  {group.species_name}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {group.detections.length} {group.detections.length > 1 ? t('video.detections') : t('video.detection')} •{' '}
                  {Math.round(group.totalDuration)}s
                </Typography>
                {(() => {
                  const providers = [...new Set(group.detections.map((d) => d.detection_provider).filter(Boolean))];
                  const providerLabels: Record<string, string> = {
                    yolo: t('video.detectionProviderYolo'),
                    frigate: t('video.detectionProviderFrigate'),
                    birdnet_mqtt: t('video.detectionProviderBirdnetMqtt'),
                  };
                  return providers.length > 0 ? (
                    <Typography variant="body2" color="text.secondary">
                      {t('video.detectionSource')}: {providers.map((p) => providerLabels[p] || p).join(', ')}
                    </Typography>
                  ) : null;
                })()}
                <Typography variant="body2" color="text.secondary">
                  {t('video.confidence')}: {group.confidenceRange}
                </Typography>
              </CardContent>
              <CardActions sx={{ pt: 0 }}>
                <Button
                  size="small"
                  component={Link}
                  to={`/species/${group.species_id}`}
                >
                  {t('video.learnMore')}
                </Button>
                {(() => {
                  const bestDet = group.detections
                    .filter((d) => d.source === 'video' && d.id)
                    .sort((a, b) => (b.confidence || 0) - (a.confidence || 0))[0];
                  return bestDet ? (
                    <INaturalistButton
                      detectionId={bestDet.id!}
                      speciesName={group.species_name}
                    />
                  ) : null;
                })()}
              </CardActions>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
};
