import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { dispenseFeed, fetchFeedInfo } from '../api/api';
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

function formatScale(
  weight: number,
  unit: string,
  updatedAt: string | undefined,
  locale: string | undefined,
): string {
  const u = (unit || 'kg').toLowerCase();
  const digits = u === 'g' && Math.abs(weight) >= 100 ? 0 : u === 'g' ? 1 : 3;
  const w = new Intl.NumberFormat(locale, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  }).format(weight);
  let time = '';
  if (updatedAt) {
    try {
      const formatted = formatLocalDateTime(updatedAt);
      if (formatted !== '—') time = formatted;
    } catch {
      /* ignore */
    }
  }
  return time ? `${w} ${u} · ${time}` : `${w} ${u}`;
}

export const FeedCard = () => {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const { isAdmin } = useProtectedArea();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; success: boolean } | null>(null);

  const { data: feedInfo } = useQuery({
    queryKey: ['feed-info'],
    queryFn: fetchFeedInfo,
    staleTime: 1000 * 30, // 30 sec
  });

  const handleDispense = async () => {
    if (!isAdmin) return;
    setLoading(true);
    setMessage(null);
    const result = await dispenseFeed();
    setLoading(false);
    setMessage({
      text: result.success ? t('feed.feedDispensed') : result.message || t('common.error'),
      success: result.success,
    });
    if (result.success) {
      queryClient.invalidateQueries({ queryKey: ['feed-info'] });
    }
  };

  const lastDispenseStr = formatLastDispense(feedInfo?.last_dispense_at ?? null);
  const feedEnabled = feedInfo?.feed_source !== 'none';
  const scale = feedInfo?.scale;
  const scaleLine =
    scale && typeof scale.weight === 'number'
      ? formatScale(scale.weight, scale.unit || 'kg', scale.updated_at, i18n.language)
      : null;

  return (
    <Paper sx={{ padding: 2, height: '100%' }}>
      <Stack spacing={2}>
        <Typography variant="h6">
          {feedEnabled ? t('feed.feederControl') : t('feed.feederIdleTitle')}
        </Typography>
        {feedEnabled && (
          <>
            {!isAdmin && (
              <Typography variant="body2" color="text.secondary">
                {t('feed.adminOnly')}
              </Typography>
            )}
            <Button
              variant="contained"
              color="primary"
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
            {message && (
              <Typography variant="body2" color={message.success ? 'success.main' : 'error.main'}>
                {message.text}
              </Typography>
            )}
          </>
        )}
        {!feedEnabled && (
          <Typography variant="body2" color="text.secondary">
            {t('feed.relayNotConfigured')}
          </Typography>
        )}
        {scaleLine && (
          <Typography variant="body2" color="text.secondary">
            {t('feed.scaleReading')}: {scaleLine}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
};
