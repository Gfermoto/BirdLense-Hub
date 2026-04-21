import { useForm } from '@tanstack/react-form';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import type { Settings } from '../../types';
import { GeneralSection } from './sections/GeneralSection';
import { ConnectionsSection } from './sections/ConnectionsSection';
import { CaptureFeederSection } from './sections/CaptureFeederSection';
import { NotificationsSection } from './sections/NotificationsSection';
import { IntegrationsSection } from './sections/IntegrationsSection';
import { ProcessorSection } from './sections/ProcessorSection';

/** Настройки: секции по смыслу (подключения → захват/кормушка → уведомления → интеграции → процессор). */
export const SettingsForm = ({
  currentSettings,
  observedSpecies,
  onSubmit,
  yamlSafeExportEnabled = false,
  yamlAdminBackupEnabled = false,
}: {
  currentSettings: Settings;
  observedSpecies: Array<{ id: number; name: string; count: number }>;
  onSubmit: (settings: Settings) => void;
  yamlSafeExportEnabled?: boolean;
  yamlAdminBackupEnabled?: boolean;
}) => {
  const { t } = useTranslation();
  const form = useForm<Settings>({
    defaultValues: currentSettings,
    onSubmit: ({ value }) => onSubmit(value),
  });

  return (
    <Box
      component="form"
      noValidate
      autoComplete="off"
      onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
        form.handleSubmit();
      }}
    >
      <Box id="settings-general">
        <GeneralSection
          form={form}
          yamlSafeExportEnabled={yamlSafeExportEnabled}
          yamlAdminBackupEnabled={yamlAdminBackupEnabled}
        />
      </Box>
      <Box id="settings-connections">
        <ConnectionsSection form={form} />
      </Box>
      <Box id="settings-capture">
        <CaptureFeederSection form={form} />
      </Box>
      <Box id="settings-notifications">
        <NotificationsSection form={form} observedSpecies={observedSpecies} />
      </Box>
      <Box id="settings-integrations">
        <IntegrationsSection form={form} />
      </Box>
      <Box id="settings-recognition">
        <ProcessorSection form={form} />
      </Box>

      <Button variant="contained" fullWidth type="submit" sx={{ mt: 4 }}>
        {t('settings.save')}
      </Button>
    </Box>
  );
};
