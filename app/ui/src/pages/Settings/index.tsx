import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import CircularProgress from '@mui/material/CircularProgress';
import Container from '@mui/material/Container';
import Snackbar from '@mui/material/Snackbar';
import Typography from '@mui/material/Typography';
import { SettingsForm } from './SettingsForm';
import { SettingsPasswordDialog } from '../../components/SettingsPasswordDialog';
import {
  fetchBirdDirectory,
  fetchSettings,
  fetchSettingsRequiresPassword,
  updateSettings,
  restartProcessor,
} from '../../api/api';
import { Settings as SettingsType, Species } from '../../types';

const useAllBirdsQuery = (select?: (species: Species[]) => any) => {
  return useQuery({
    queryKey: ['bird-directory'],
    queryFn: fetchBirdDirectory,
    select: select,
  });
};

export const Settings: React.FC = () => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [showSuccessAlert, setShowSuccessAlert] = useState(false);
  const [restartMessage, setRestartMessage] = useState<{ type: 'success' | 'error'; textKey: string; apiMessage?: string } | null>(null);
  const [unlocked, setUnlocked] = useState(false);

  const { data: requiresPassword, isLoading: isLoadingRequires } = useQuery({
    queryKey: ['settings-requires-password'],
    queryFn: fetchSettingsRequiresPassword,
  });

  const { data: settings, isLoading: isLoadingSettings } = useQuery({
    queryKey: ['settings'],
    queryFn: fetchSettings,
    enabled: !requiresPassword || unlocked,
  });

  const { isLoading: isLoadingAllSpecies } = useAllBirdsQuery();
  const { data: observedSpecies } = useAllBirdsQuery((allSpecies) =>
    allSpecies.filter((species) => (species.count as number) > 0),
  );
  const { data: birdFamilies } = useAllBirdsQuery((allSpecies) => {
    const birdSpecies = allSpecies.find((s) => s.name === 'Birds');
    return allSpecies.filter(
      (species) => species.parent_id === birdSpecies?.id,
    );
  });

  const updateMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: async () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] });
      setShowSuccessAlert(true);
      const result = await restartProcessor();
      setRestartMessage(
        result.success
          ? { type: 'success', textKey: 'settings.savedRestart' }
          : { type: 'error', textKey: 'settings.restartFailed', apiMessage: result.message },
      );
    },
  });

  const showPasswordDialog = requiresPassword && !unlocked;
  const isLoading = isLoadingRequires || isLoadingSettings || isLoadingAllSpecies;

  if (isLoadingRequires)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );

  if (showPasswordDialog) {
    return (
      <Container maxWidth="md" sx={{ pb: 5 }}>
        <Typography variant="h4" gutterBottom>
          {t('settings.updateTitle')}
        </Typography>
        <Typography color="text.secondary" sx={{ mb: 3 }}>
          {t('settings.passwordRequired')}
        </Typography>
        <SettingsPasswordDialog
          open
          onSuccess={() => setUnlocked(true)}
        />
      </Container>
    );
  }

  if (isLoading || isLoadingAllSpecies)
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center' }}>
        <CircularProgress />
      </Box>
    );

  return (
    <Container maxWidth="md" sx={{ pb: 5 }}>
      <Typography variant="h4" gutterBottom>
        {t('settings.updateTitle')}
      </Typography>
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
        currentSettings={settings as SettingsType}
        observedSpecies={observedSpecies}
        birdFamilies={birdFamilies}
        onSubmit={updateMutation.mutate}
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
  );
};
