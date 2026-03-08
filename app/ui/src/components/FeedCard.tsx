import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import RestaurantIcon from '@mui/icons-material/Restaurant';
import { useState } from 'react';
import { dispenseFeed } from '../api/api';

export const FeedCard = () => {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const handleDispense = async () => {
    setLoading(true);
    setMessage(null);
    const result = await dispenseFeed();
    setLoading(false);
    setMessage(result.success ? 'Feed dispensed' : result.message || 'Error');
  };

  return (
    <Paper sx={{ padding: 2, height: '100%' }}>
      <Stack spacing={2}>
        <Typography variant="h6">Feeder Control</Typography>
        <Button
          variant="contained"
          color="primary"
          startIcon={<RestaurantIcon />}
          onClick={handleDispense}
          disabled={loading}
        >
          {loading ? 'Dispensing...' : 'Dispense Feed'}
        </Button>
        {message && (
          <Typography variant="body2" color={message.startsWith('Feed') ? 'success.main' : 'error.main'}>
            {message}
          </Typography>
        )}
      </Stack>
    </Paper>
  );
};
