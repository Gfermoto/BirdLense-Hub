import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';
import { dispenseFeed } from '../api/api';

export const FeedCard = () => {
  const { t } = useTranslation();
  const { isAdmin } = useProtectedArea();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; success: boolean } | null>(null);

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
  };

  return (
    <Paper sx={{ padding: 2, height: '100%' }}>
      <Stack spacing={2}>
        <Typography variant="h6">{t('feed.feederControl')}</Typography>
        {!isAdmin && (
          <Typography variant="body2" color="text.secondary">
            {t('unknowns.passwordRequired')}{' '}
            <Link to="/settings" style={{ fontWeight: 600 }}>
              {t('nav.settings')}
            </Link>
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
        {message && (
          <Typography variant="body2" color={message.success ? 'success.main' : 'error.main'}>
            {message.text}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
};
