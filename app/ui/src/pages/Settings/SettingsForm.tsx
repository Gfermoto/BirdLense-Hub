import { useForm } from '@tanstack/react-form';
import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import type { Settings } from '../../types';
import { GeneralSection } from './sections/GeneralSection';
import { ConnectionsSection } from './sections/ConnectionsSection';
import { CaptureFeederSection } from './sections/CaptureFeederSection';
import { NotificationsSection } from './sections/NotificationsSection';
import { IntegrationsSection } from './sections/IntegrationsSection';
import { ProcessorSection } from './sections/ProcessorSection';
import type { SettingsTier } from './settingsTier';
import {
  isBasicTier,
  showAdvancedProcessorBlocks,
  showExpertTools,
} from './settingsTier';

/** Настройки: секции по смыслу (подключения → захват/кормушка → уведомления → интеграции → процессор). */
export const SettingsForm = ({
  currentSettings,
  observedSpecies,
  onSubmit,
  yamlSafeExportEnabled = false,
  yamlAdminBackupEnabled = false,
  settingsTier = 'basic',
}: {
  currentSettings: Settings;
  observedSpecies: Array<{ id: number; name: string; count: number }>;
  onSubmit: (settings: Settings) => void;
  yamlSafeExportEnabled?: boolean;
  yamlAdminBackupEnabled?: boolean;
  settingsTier?: SettingsTier;
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
        {isBasicTier(settingsTier) ? (
          <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
            {t('settings.simpleModeHint')}
          </Alert>
        ) : null}
        <GeneralSection
          form={form}
          yamlSafeExportEnabled={
            yamlSafeExportEnabled && showAdvancedProcessorBlocks(settingsTier)
          }
          yamlAdminBackupEnabled={
            yamlAdminBackupEnabled && showExpertTools(settingsTier)
          }
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
        <IntegrationsSection
          form={form}
          settingsTier={settingsTier}
        />
      </Box>
      <Box id="settings-recognition">
        <ProcessorSection form={form} settingsTier={settingsTier} />
      </Box>

      <Button variant="contained" fullWidth type="submit" sx={{ mt: 4 }}>
        {t('settings.save')}
      </Button>
    </Box>
  );
};
