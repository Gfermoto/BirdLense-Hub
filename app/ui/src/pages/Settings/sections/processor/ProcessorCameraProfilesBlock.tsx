import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Typography from '@mui/material/Typography';
import Alert from '@mui/material/Alert';
import { ServiceBlock } from '../../shared/ServiceBlock';
import { CameraTuningFieldsGrid } from '../../shared/CameraTuningFieldsGrid';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorCameraProfilesBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorCameraProfilesTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorCameraProfilesDesc')}
      </Typography>
      <Alert severity="info" variant="outlined" sx={{ mb: 2 }}>
        {t('settings.processorCameraProfilesRoleHint')}
      </Alert>
      <form.Subscribe selector={(state) => state.values.video?.cameras ?? []}>
        {(cameras) =>
          cameras.map((cam) => {
            const cameraId = String(cam?.id ?? cam?.stream_name ?? '').trim();
            if (!cameraId) return null;
            const role = String(cam?.tuning_role ?? '').trim();
            return (
              <Accordion key={cameraId} disableGutters sx={{ mb: 1 }}>
                <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                  <Typography variant="subtitle2">
                    {cam?.name || cameraId}
                    {role ? ` · ${role}` : ''}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails>
                  <CameraTuningFieldsGrid
                    form={form}
                    namePrefix={`processor.camera_overrides.${cameraId}`}
                  />
                </AccordionDetails>
              </Accordion>
            );
          })
        }
      </form.Subscribe>
      <form.Subscribe selector={(state) => state.values.video?.cameras ?? []}>
        {(cameras) =>
          cameras.every((c) => !String(c?.id ?? c?.stream_name ?? '').trim()) ? (
            <Typography variant="body2" color="text.secondary">
              {t('settings.processorCameraProfilesEmpty')}
            </Typography>
          ) : null
        }
      </form.Subscribe>
    </ServiceBlock>
  );
}
