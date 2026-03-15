import React, { useState } from 'react';
import type { SpeciesVisit } from '../types';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Typography from '@mui/material/Typography';
import { SpeciesIcon } from './SpeciesIcon';
import Chip from '@mui/material/Chip';
import Box from '@mui/material/Box';
import CardActionArea from '@mui/material/CardActionArea';
import Collapse from '@mui/material/Collapse';
import IconButton from '@mui/material/IconButton';
import ExpandMore from '@mui/icons-material/ExpandMore';
import ExpandLess from '@mui/icons-material/ExpandLess';
import AccessTime from '@mui/icons-material/AccessTime';
import Thermostat from '@mui/icons-material/Thermostat';
import CalendarToday from '@mui/icons-material/CalendarToday';
import Groups from '@mui/icons-material/Groups';
import VideoCall from '@mui/icons-material/VideoCall';
import Mic from '@mui/icons-material/Mic';
import Share from '@mui/icons-material/Share';
import Tooltip from '@mui/material/Tooltip';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import { useNavigate } from 'react-router-dom';
import { useTheme } from '@mui/material/styles';
import { useTranslation } from 'react-i18next';
import { downloadDetectionCropForINaturalist } from '../api/api';

const DetectionItem = ({
  detection,
  speciesName,
  onClick,
  isLastInGroup,
}: {
  detection: SpeciesVisit['detections'][0];
  speciesName: string;
  onClick: () => void;
  isLastInGroup: boolean;
}) => {
  const theme = useTheme();
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleINaturalist = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!detection.id || detection.source !== 'video') return;
    setLoading(true);
    setErrorMsg(null);
    try {
      await downloadDetectionCropForINaturalist(detection.id, speciesName);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      setErrorMsg(msg);
      console.error('iNaturalist export failed:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Box>
      <CardActionArea
        onClick={onClick}
        sx={{
          p: 1.5,
          borderRadius: 1,
          backgroundColor: theme.palette.action.hover,
        }}
      >
        <Box display="flex" alignItems="center" gap={1.5}>
          <Box display="flex" alignItems="center">
            {detection.source === 'video' ? (
              <VideoCall color="primary" fontSize="small" />
            ) : (
              <Mic color="secondary" fontSize="small" />
            )}
          </Box>
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ minWidth: 65 }}
          >
            {new Date(detection.start_time).toLocaleTimeString()}
          </Typography>
          <Chip
            label={`${Math.round(detection.confidence * 100)}%`}
            size="small"
            color={detection.source === 'video' ? 'primary' : 'secondary'}
            sx={{
              height: 24,
              '& .MuiChip-label': { px: 1, fontSize: '0.75rem' },
            }}
          />
          <Typography
            variant="body2"
            color="text.secondary"
            sx={{ ml: 'auto' }}
          >
            {Math.round(
              (new Date(detection.end_time).getTime() -
                new Date(detection.start_time).getTime()) /
                1000,
            )}
            s
          </Typography>
          {detection.source === 'video' && detection.id && (
            <Tooltip title={t('common.iNaturalist')}>
              <span>
                <IconButton
                  size="small"
                  onClick={handleINaturalist}
                  disabled={loading}
                  sx={{ p: 0.5 }}
                  aria-label={t('common.iNaturalist')}
                >
                  <Share fontSize="small" />
                </IconButton>
              </span>
            </Tooltip>
          )}
        </Box>
      </CardActionArea>
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
      {isLastInGroup && <Box mx={1.5} my={1} />}
    </Box>
  );
};

const groupDetectionsByVideo = (detections: SpeciesVisit['detections']) => {
  return detections.reduce<SpeciesVisit['detections'][]>((acc, detection) => {
    if (
      acc.length === 0 ||
      acc[acc.length - 1][0].video_id !== detection.video_id
    ) {
      acc.push([detection]);
    } else {
      acc[acc.length - 1].push(detection);
    }
    return acc;
  }, []);
};

export interface VisitCardProps {
  visit: SpeciesVisit;
  compact?: boolean;
  showDateTime?: boolean;
}

export const VisitCard = ({
  visit,
  compact = false,
  showDateTime = false,
}: VisitCardProps) => {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(false);

  const startDateTime = new Date(visit.start_time);
  const isToday = new Date().toDateString() === startDateTime.toDateString();

  const formatDateTime = () => {
    if (isToday) {
      return `Today at ${startDateTime.toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
      })}`;
    }
    return startDateTime.toLocaleString([], {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card>
      <CardContent sx={{ '&:last-child': { pb: 2 } }}>
        <Box display="flex" alignItems="flex-start" gap={2}>
          <SpeciesIcon
            speciesName={visit.species.name}
            imageUrl={visit.species.image_url}
            size={compact ? 44 : 48}
          />
          <Box flex={1} minWidth={0}>
            <Box display="flex" alignItems="center" gap={1}>
              <Box flex={1}>
                <Typography
                  variant={compact ? 'body1' : 'h6'}
                  component="div"
                  sx={{
                    lineHeight: compact ? 1.4 : 1.5,
                    wordBreak: 'break-word',
                  }}
                >
                  {visit.species.name}
                </Typography>
                {showDateTime && (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 0.5,
                      mt: 0.5,
                    }}
                  >
                    <CalendarToday sx={{ fontSize: 14 }} />
                    {formatDateTime()}
                  </Typography>
                )}
              </Box>
              <IconButton
                size="small"
                onClick={() => setExpanded(!expanded)}
                sx={{ mt: -0.5 }}
              >
                {expanded ? <ExpandLess /> : <ExpandMore />}
              </IconButton>
            </Box>
            <Box display="flex" gap={1.5} mt={1.5} flexWrap="nowrap">
              <Chip
                icon={
                  <Box display="flex" alignItems="center">
                    <Groups sx={{ fontSize: 18 }} />
                  </Box>
                }
                label={visit.max_simultaneous}
                size="small"
                sx={{ height: 28 }}
              />
              <Chip
                icon={
                  <Box display="flex" alignItems="center">
                    <AccessTime sx={{ fontSize: 18 }} />
                  </Box>
                }
                label={`${Math.round(
                  (new Date(visit.end_time).getTime() -
                    new Date(visit.start_time).getTime()) /
                    1000,
                )}s`}
                size="small"
                sx={{ height: 28 }}
              />
              {visit.weather?.temp && (
                <Chip
                  icon={
                    <Box display="flex" alignItems="center">
                      <Thermostat sx={{ fontSize: 18 }} />
                    </Box>
                  }
                  label={`${visit.weather.temp}°C`}
                  size="small"
                  sx={{ height: 28 }}
                />
              )}
            </Box>
          </Box>
        </Box>
        <Collapse in={expanded} timeout="auto">
          <Box mt={2}>
            {groupDetectionsByVideo(visit.detections).map(
              (group, groupIndex) => (
                <Box key={`group-${groupIndex}`}>
                  {group.map((detection, index) => (
                    <DetectionItem
                      key={`${detection.video_id}-${index}`}
                      detection={detection}
                      speciesName={visit.species.name}
                      onClick={() => navigate(`/videos/${detection.video_id}`)}
                      isLastInGroup={index === group.length - 1}
                    />
                  ))}
                </Box>
              ),
            )}
          </Box>
        </Collapse>
      </CardContent>
    </Card>
  );
};
