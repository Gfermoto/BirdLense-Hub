import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Snackbar from '@mui/material/Snackbar';
import { SettingsForm } from './SettingsForm';
import { restartProcessor } from '../../api/notificationsProcessor';
import { updateSettings } from '../../api/settingsSession';
import { queryKeys } from '../../api/queryKeys';
import {
  useObservedSpeciesQuery,
  useSettingsQuery,
} from '../../hooks/useSettingsQueries';
import { Settings as SettingsType } from '../../types';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageModeToggle, type PageMode } from '../../components/PageModeToggle';
import {
  loadSettingsTier,
  saveSettingsTier,
  type SettingsTier,
} from './settingsTier';
import { PageHeader } from '../../components/PageHeader';
import { PageLoadingState, PageMessageState } from '../../components/PageState';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export const Settings: React.FC = () => {
  const { t } = useTranslation();
  const location = useLocation();
  useDocumentTitle(t('nav.settings'));
  const queryClient = useQueryClient();
  const [showSuccessAlert, setShowSuccessAlert] = useState(false);
  const [deprecatedKeysAlert, setDeprecatedKeysAlert] = useState<string[] | null>(
    null,
  );
  const [mode, setMode] = useState<PageMode>(() => loadSettingsTier());
  const handleModeChange = (next: PageMode) => {
    setMode(next);
    saveSettingsTier(next as SettingsTier);
  };
  const [restartMessage, setRestartMessage] = useState<{
    type: 'success' | 'error';
    textKey: string;
    apiMessage?: string;
  } | null>(null);
  const { isAdmin, canEdit } = useProtectedArea();

  /** Только админ видит страницу (ProtectedRoute requireAdmin) — грузим настройки в том же условии. */
  const { data: settings, isLoading: isLoadingSettings } =
    useSettingsQuery(isAdmin);

  const { data: observedSpecies, isLoading: isLoadingObserved } =
    useObservedSpeciesQuery();

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: async (data: Record<string, unknown> | undefined) => {
      const warnings = data?._settings_warnings as
        | { deprecated_keys_present?: string[] }
        | undefined;
      const deprecated = warnings?.deprecated_keys_present;
      setDeprecatedKeysAlert(
        Array.isArray(deprecated) && deprecated.length > 0 ? deprecated : null,
      );
      queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
      setShowSuccessAlert(true);
      const result = await restartProcessor();
      setRestartMessage(
        result.success
          ? { type: 'success', textKey: 'settings.savedRestart' }
          : {
              type: 'error',
              textKey: 'settings.restartFailed',
              apiMessage: result.message,
            },
      );
    },
    onError: (err: unknown) => {
      const msg = err instanceof Error ? err.message : t('settings.saveError');
      setRestartMessage({
        type: 'error',
        textKey: 'settings.saveError',
        apiMessage: msg,
      });
    },
  });

  const isLoading = isLoadingSettings || isLoadingObserved;
  const settingsError = !isLoadingSettings && !settings;
  const [formKey, setFormKey] = useState(0);
  useEffect(() => {
    if (settings && Object.keys(settings).length > 0) {
      setFormKey((key) => key + 1);
    }
  }, [settings]);

  useEffect(() => {
    const h = location.hash.replace(/^#/, '');
    if (h !== 'processor-models') return;
    const id = 'processor-models';
    requestAnimationFrame(() => {
      document
        .getElementById(id)
        ?.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  }, [location.hash, isLoading, settings]);

  return (
    <ProtectedRoute title={t('settings.updateTitle')} requireAdmin>
      {isLoading ? (
        <PageLoadingState label={t('common.loading')} />
      ) : settingsError ? (
        <PageMessageState
          title={t('settings.updateTitle')}
          message={t('settings.settingsLoadFailed')}
          severity="error"
        />
      ) : (
        <Box
          display="grid"
          gap={4}
          sx={{ pb: 5, minWidth: 0, maxWidth: '100%' }}
        >
          <PageHeader
            title={t('settings.updateTitle')}
            description={`${t('settings.pageDescription')} ${t('settings.restartInfo')}`}
            actions={
              <PageModeToggle
                value={mode}
                onChange={handleModeChange}
                showExpert
                simpleLabel={t('settings.modeOverview')}
                advancedLabel={t('settings.modeWorkspace')}
                expertLabel={t('settings.modeExpert')}
                ariaLabel={t('settings.modeAria')}
              />
            }
            titleVariant="h3"
          />
          <Alert severity="info" variant="outlined" sx={{ mb: 0 }}>
            {t('settings.loaded')}
          </Alert>
          {restartMessage && (
            <Alert
              severity={restartMessage.type}
              variant="outlined"
              sx={{ mb: 2 }}
              onClose={() => setRestartMessage(null)}
            >
              {restartMessage.apiMessage || t(restartMessage.textKey)}
            </Alert>
          )}
          {deprecatedKeysAlert && deprecatedKeysAlert.length > 0 && (
            <Alert
              severity="warning"
              variant="outlined"
              sx={{ mb: 2 }}
              onClose={() => setDeprecatedKeysAlert(null)}
            >
              {t('settings.deprecatedKeysAfterSave', {
                count: deprecatedKeysAlert.length,
                keys: deprecatedKeysAlert.join(', '),
              })}
            </Alert>
          )}
          <SettingsForm
            key={formKey}
            currentSettings={settings as SettingsType}
            observedSpecies={observedSpecies ?? []}
            onSubmit={updateMutation.mutate}
            yamlSafeExportEnabled={canEdit}
            yamlAdminBackupEnabled={isAdmin}
            settingsTier={mode}
          />
          <Snackbar
            open={showSuccessAlert}
            autoHideDuration={6000}
            onClose={() => setShowSuccessAlert(false)}
          >
            <Alert
              onClose={() => setShowSuccessAlert(false)}
              severity="success"
              variant="filled"
              elevation={6}
              sx={{ width: '100%' }}
            >
              {t('settings.savedRestarting')}
            </Alert>
          </Snackbar>
        </Box>
      )}
    </ProtectedRoute>
  );
};
