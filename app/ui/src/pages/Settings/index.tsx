import React, { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Container from '@mui/material/Container';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { SettingsForm } from './SettingsForm';
import { updateSettings, restartProcessor } from '../../api/api';
import { queryKeys } from '../../api/queryKeys';
import { useObservedSpeciesQuery, useSettingsQuery } from '../../hooks/useSettingsQueries';
import { Settings as SettingsType } from '../../types';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { ProtectedRoute } from '../../components/ProtectedRoute';

export const Settings: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showSuccessAlert, setShowSuccessAlert] = useState(false);
  const [restartMessage, setRestartMessage] = useState<{ type: 'success' | 'error'; textKey: string; apiMessage?: string } | null>(null);
  const { requiresPassword, isAdmin, canEdit } = useProtectedArea();

  const { data: settings, isLoading: isLoadingSettings } = useSettingsQuery(
    !requiresPassword || canEdit,
  );

  const { data: observedSpecies, isLoading: isLoadingObserved } = useObservedSpeciesQuery();

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
      setShowSuccessAlert(true);
      const result = await restartProcessor();
      setRestartMessage(
        result.success
          ? { type: 'success', textKey: 'settings.savedRestart' }
          : { type: 'error', textKey: 'settings.restartFailed', apiMessage: result.message },
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : t('settings.saveError');
      setRestartMessage({ type: 'error', textKey: 'settings.saveError', apiMessage: msg });
    },
  });

  const isLoading = isLoadingSettings || isLoadingObserved;
  const settingsError = !isLoadingSettings && !settings;
  const [formKey, setFormKey] = useState(0);
  const hasInitializedForm = useRef(false);
  useEffect(() => {
    if (settings && Object.keys(settings).length > 0 && !hasInitializedForm.current) {
      hasInitializedForm.current = true;
      setFormKey(1);
    }
  }, [settings]);

  return (
    <ProtectedRoute title={t('settings.updateTitle')} requireAdmin={false}>
      {isLoading ? (
        <Box sx={{ display: 'flex', justifyContent: 'center' }}>
          <CircularProgress />
        </Box>
      ) : settingsError ? (
        <Container maxWidth="md" sx={{ pb: 5 }}>
          <Typography variant="h4" gutterBottom>
            {t('settings.updateTitle')}
          </Typography>
          <Alert severity="error" sx={{ mt: 2 }}>
            {t('settings.settingsLoadFailed')}
          </Alert>
        </Container>
      ) : (
        <Container maxWidth="md" sx={{ pb: 5 }}>
          <Typography variant="h4" gutterBottom>
            {t('settings.updateTitle')}
          </Typography>
          <Alert severity="success" sx={{ mb: 2 }}>
            {t('settings.loaded')}
          </Alert>
          <Alert severity="info" sx={{ mb: 3 }}>
            {t('settings.restartInfo')}
          </Alert>
          {restartMessage && (
            <Alert
              severity={restartMessage.type}
              sx={{ mb: 2 }}
              onClose={() => setRestartMessage(null)}
            >
              {restartMessage.apiMessage || t(restartMessage.textKey)}
            </Alert>
          )}
          <SettingsForm
            key={formKey}
            currentSettings={settings as SettingsType}
            observedSpecies={observedSpecies ?? []}
            onSubmit={updateMutation.mutate}
            yamlSafeExportEnabled={canEdit}
            yamlAdminBackupEnabled={isAdmin}
          />
          <Snackbar
            open={showSuccessAlert}
            autoHideDuration={6000}
            onClose={() => setShowSuccessAlert(false)}
          >
            <Alert
              onClose={() => setShowSuccessAlert(false)}
              severity="success"
              sx={{ width: '100%' }}
            >
              {t('settings.savedRestarting')}
            </Alert>
          </Snackbar>
        </Container>
      )}
    </ProtectedRoute>
  );
};
