import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from '../../shared/ServiceBlock';
import { CameraTuningFieldsGrid } from '../../shared/CameraTuningFieldsGrid';
import { CAMERA_TUNING_ROLES } from '../../shared/cameraTuningFields';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

const ROLE_LABEL_KEYS: Record<string, string> = {
  feeder_close: 'settings.cameraTuningRoleFeederClose',
  feeder_far: 'settings.cameraTuningRoleFeederFar',
};

export function ProcessorRolePresetsBlock({ form }: Props) {
  const { t } = useTranslation();
  const roles = CAMERA_TUNING_ROLES.filter((r) => r !== 'custom');

  return (
    <ServiceBlock title={t('settings.processorRolePresetsTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorRolePresetsDesc')}
      </Typography>
      {roles.map((role) => (
        <Accordion key={role} disableGutters sx={{ mb: 1 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">{t(ROLE_LABEL_KEYS[role] ?? role)}</Typography>
          </AccordionSummary>
          <AccordionDetails>
            <CameraTuningFieldsGrid
              form={form}
              namePrefix={`processor.camera_tuning_by_role.${role}`}
            />
          </AccordionDetails>
        </Accordion>
      ))}
    </ServiceBlock>
  );
}
