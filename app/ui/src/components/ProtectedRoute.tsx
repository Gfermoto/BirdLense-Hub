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
  requireAdmin?: boolean;
}

/**
 * Wraps protected content (Settings, System). Shows password dialog when
 * access is restricted, or network error when check-access fails.
 */
export function ProtectedRoute({
  children,
  title,
  requireAdmin = true,
}: ProtectedRouteProps) {
  const { t } = useTranslation();
  const {
    requiresPassword,
    unlocked,
    isAdmin,
    setUnlocked,
    isLoading,
    accessError,
  } = useProtectedArea();

  const hasAccess = requireAdmin ? isAdmin : unlocked;
  const showPasswordDialog = requiresPassword && !hasAccess;
  const showNetworkError = accessError === 'network' && !hasAccess;

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
          {t('protected.passwordRequired')}
        </Typography>
        <SettingsPasswordDialog
          open
          requireAdmin={requireAdmin}
          onSuccess={(role) => setUnlocked(true, role || 'admin')}
        />
      </Container>
    );
  }

  return <>{children}</>;
}
