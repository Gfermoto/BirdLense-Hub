import React from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import { SettingsPasswordDialog } from './SettingsPasswordDialog';
import { useProtectedArea } from '../contexts/ProtectedAreaContext';
import { PageHeader } from './PageHeader';
import { PageLoadingState, PageMessageState } from './PageState';

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
    return <PageLoadingState label={t('common.loading')} />;
  }

  if (showNetworkError) {
    return (
      <PageMessageState
        title={title}
        message={t('settings.accessErrorNetwork')}
        severity="error"
      />
    );
  }

  if (showPasswordDialog) {
    return (
      <Box sx={{ pb: 5, maxWidth: 720 }}>
        <PageHeader
          title={title}
          description={t('protected.passwordRequired')}
          titleVariant="h3"
          sx={{ mb: 3 }}
        />
        <SettingsPasswordDialog
          open
          requireAdmin={requireAdmin}
          onSuccess={(role) => setUnlocked(true, role || 'admin')}
        />
      </Box>
    );
  }

  return <>{children}</>;
}
