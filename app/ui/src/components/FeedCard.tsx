import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import PetsIcon from '@mui/icons-material/Pets';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import ScaleIcon from '@mui/icons-material/Scale';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { dispenseFeed, fetchFeedInfo, postScaleTare } from '../api/birdFoodFeed';
import { queryKeys } from '../api/queryKeys';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';
import { formatLocalDateTime } from '../util';

function formatLastDispense(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const formatted = formatLocalDateTime(iso);
    return formatted === '—' ? null : formatted;
  } catch {
    return null;
  }
}

const SCALE_STALE_MS = 120_000;

function formatScaleValue(
  weight: number,
  unit: string,
  locale: string | undefined,
): string {
  const u = (unit || 'g').toLowerCase();
  const digits = u === 'g' && Math.abs(weight) >= 100 ? 0 : u === 'g' ? 1 : 3;
  const w = new Intl.NumberFormat(locale, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(weight);
  return `${w} ${u}`;
}

function formatScaleUpdatedLine(updatedAt: string | undefined): string | null {
  if (!updatedAt) return null;
  try {
    const formatted = formatLocalDateTime(updatedAt);
    return formatted === '—' ? null : formatted;
  } catch {
    return null;
  }
}

function isScaleReadingStale(updatedAt: string | undefined): boolean {
  if (!updatedAt) return false;
  const t = Date.parse(updatedAt);
  if (Number.isNaN(t)) return false;
  return Date.now() - t > SCALE_STALE_MS;
}

export const FeedCard = () => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { isAdmin, canEdit } = useProtectedArea();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    text: string;
    success: boolean;
  } | null>(null);
  const [tareLoading, setTareLoading] = useState(false);

  const { data: feedInfo } = useQuery({
    queryKey: queryKeys.feed.info,
    queryFn: fetchFeedInfo,
    staleTime: 1000 * 15,
    refetchInterval: (query) =>
      query.state.data?.scales_enabled ? 10_000 : false,
  });

  const handleDispense = async () => {
    if (!isAdmin) return;
    setLoading(true);
    setMessage(null);
    const result = await dispenseFeed();
    setLoading(false);
    setMessage({
      text: result.success
        ? t('feed.feedDispensed')
        : result.message || t('common.error'),
      success: result.success,
    });
    if (result.success) {
      queryClient.invalidateQueries({ queryKey: queryKeys.feed.info });
    }
  };

  const lastDispenseStr = formatLastDispense(
    feedInfo?.last_dispense_at ?? null,
  );
  const feedEnabled = feedInfo?.feed_source !== 'none';
  const scalesEnabled = Boolean(feedInfo?.scales_enabled);
  const scalesSource = feedInfo?.scales_source;
  const scale = feedInfo?.scale;
  const weightDefined = scale && typeof scale.weight === 'number';
  const weightStr = weightDefined
    ? formatScaleValue(scale.weight as number, scale.unit || 'g', i18n.language)
    : null;
  const updatedLine = weightDefined
    ? formatScaleUpdatedLine(scale?.updated_at)
    : null;
  const scaleStale = weightDefined
    ? isScaleReadingStale(scale?.updated_at)
    : false;
  const birdPresentDefined = scale && typeof scale.bird_present === 'boolean';
  const tareAvailable = Boolean(feedInfo?.scale_tare_available);
  const scaleNoDataLabelKey =
    scalesSource === 'esphome' ? 'feed.scaleNoDataEsp' : 'feed.scaleNoData';

  const handleScaleTare = async () => {
    if (!canEdit) return;
    setTareLoading(true);
    setMessage(null);
    const result = await postScaleTare();
    setTareLoading(false);
    setMessage({
      text: result.success
        ? t('feed.scaleTareOk')
        : result.message || t('feed.scaleTareFail'),
      success: result.success,
    });
    if (result.success) {
      queryClient.invalidateQueries({ queryKey: queryKeys.feed.info });
    }
  };

  return (
    <Paper sx={{ padding: 2, height: '100%' }}>
      <Stack spacing={2}>
        <Typography variant="h6">
          {feedEnabled ? t('feed.feederControl') : t('feed.feederIdleTitle')}
        </Typography>
        {feedEnabled && (
          <>
            <Button
              variant="contained"
              color="primary"
              sx={{
                // WCAG AA: white text on emerald 500 fails contrast (2.53:1).
                backgroundColor: '#047857',
                color: '#ffffff',
                '&:hover': { backgroundColor: '#065f46' },
              }}
              startIcon={<RestaurantIcon />}
              onClick={handleDispense}
              disabled={loading || !isAdmin}
            >
              {loading ? t('feed.dispensing') : t('feed.dispenseFeed')}
            </Button>
            {lastDispenseStr && (
              <Typography variant="caption" color="text.secondary">
                {t('feed.lastDispense')}: {lastDispenseStr}
              </Typography>
            )}
          </>
        )}
        {!feedEnabled && (
          <Typography variant="body2" color="text.secondary">
            {t('feed.relayNotConfigured')}
          </Typography>
        )}
        {scalesEnabled && (
          <>
            <Divider />
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {t('feed.scalesSection')}
            </Typography>
            {!scale && (
              <Typography variant="body2" color="text.secondary">
                {t(scaleNoDataLabelKey)}
              </Typography>
            )}
            {weightDefined && weightStr && (
              <Box>
                <Typography
                  component="span"
                  variant="h5"
                  fontWeight={600}
                  sx={{ mr: 0.5 }}
                >
                  {weightStr}
                </Typography>
                {updatedLine && (
                  <Typography
                    variant="caption"
                    color="text.secondary"
                    display="block"
                  >
                    {t('feed.scaleUpdatedAt')}: {updatedLine}
                  </Typography>
                )}
                {scaleStale && (
                  <Typography
                    variant="caption"
                    color="warning.main"
                    display="block"
                  >
                    {t('feed.scaleStaleHint')}
                  </Typography>
                )}
              </Box>
            )}
            {birdPresentDefined && (
              <Chip
                size="small"
                icon={<PetsIcon />}
                label={
                  scale!.bird_present
                    ? t('feed.birdPresentOn')
                    : t('feed.birdPresentOff')
                }
                color={scale!.bird_present ? 'success' : 'default'}
                variant={scale!.bird_present ? 'filled' : 'outlined'}
              />
            )}
            {tareAvailable && canEdit && (
              <Button
                variant="outlined"
                size="small"
                startIcon={<ScaleIcon />}
                onClick={handleScaleTare}
                disabled={tareLoading}
              >
                {tareLoading ? t('feed.scaleTaring') : t('feed.scaleTare')}
              </Button>
            )}
          </>
        )}
        {message && (
          <Typography
            variant="body2"
            color={message.success ? 'success.main' : 'error.main'}
          >
            {message.text}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
};
