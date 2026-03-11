import React from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Container from '@mui/material/Container';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import { SettingsPasswordDialog } from './SettingsPasswordDialog';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';

interface ProtectedRouteProps {
  children: React.ReactNode;
  title: string;
}

/**
 * Wraps protected content (Settings, System). Shows password dialog when
 * access is restricted, or network error when check-access fails.
 */
export function ProtectedRoute({ children, title }: ProtectedRouteProps) {
  const { t } = useTranslation();
  const {
    requiresPassword,
    unlocked,
    setUnlocked,
    isLoading,
    accessError,
  } = useProtectedArea();

  const showPasswordDialog = requiresPassword && !unlocked;
  const showNetworkError = accessError === 'network' && !unlocked;

  if (isLoading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );
  }

  if (showNetworkError) {
    return (
      <Container maxWidth="md" sx={{ pb: 5 }}>
        <Typography variant="h4" gutterBottom>
          {title}
        </Typography>
        <Alert severity="error" sx={{ mt: 2 }}>
          {t('settings.accessErrorNetwork')}
        </Alert>
      </Container>
    );
  }

  if (showPasswordDialog) {
    return (
      <Container maxWidth="md" sx={{ pb: 5 }}>
        <Typography variant="h4" gutterBottom>
          {title}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          {t('settings.passwordRequired')}
        </Typography>
        <SettingsPasswordDialog open onSuccess={() => setUnlocked(true)} />
      </Container>
    );
  }

  return <>{children}</>;
}
