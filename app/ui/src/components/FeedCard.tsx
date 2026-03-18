import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import Box from '@mui/material/Box';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import FavoriteIcon from '@mui/icons-material/Favorite';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { dispenseFeed, fetchFeedInfo } from '../api/api';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';

function formatLastDispense(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return null;
    return d.toLocaleString(undefined, {
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return null;
  }
}

export const FeedCard = () => {
  const { t } = useTranslation();
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
  const donateUrl = feedInfo?.donate_url;
  const feedEnabled = feedInfo?.feed_source !== 'none';

  return (
    <Paper sx={{ padding: 2, height: '100%' }}>
      <Stack spacing={2}>
        <Typography variant="h6">
          {feedEnabled ? t('feed.feederControl') : t('feed.supportTitle')}
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
        <Button
          size="small"
          variant="outlined"
          startIcon={
            <Box
              component="span"
              sx={{
                display: 'inline-flex',
                animation: 'feedHeartPulse 1.5s ease-in-out infinite',
                '@keyframes feedHeartPulse': {
                  '0%, 100%': { opacity: 1, transform: 'scale(1)' },
                  '50%': { opacity: 0.85, transform: 'scale(1.1)' },
                },
              }}
            >
              <FavoriteIcon sx={{ color: 'rgba(251, 191, 36, 0.95)', fontSize: 20 }} />
            </Box>
          }
          href={donateUrl || undefined}
          target={donateUrl ? '_blank' : undefined}
          rel={donateUrl ? 'noopener noreferrer' : undefined}
          disabled={!donateUrl}
          title={!donateUrl ? t('feed.supportPlaceholder') : undefined}
        >
          {donateUrl ? t('feed.support') : t('feed.supportPlaceholder')}
        </Button>
      </Stack>
    </Paper>
  );
};
