import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { dispenseFeed } from '../api/api';

export const FeedCard = () => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{ text: string; success: boolean } | null>(null);

  const handleDispense = async () => {
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
        <Button
          variant="contained"
          color="primary"
          startIcon={<RestaurantIcon />}
          onClick={handleDispense}
          disabled={loading}
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
