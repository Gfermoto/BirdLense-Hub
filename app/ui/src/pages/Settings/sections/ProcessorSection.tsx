import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { Settings } from '../../../types';
import { ProcessorConfidenceBlock } from './processor/ProcessorConfidenceBlock';
import { ProcessorSessionTimingBlock } from './processor/ProcessorSessionTimingBlock';
import { ProcessorMultiCameraBirdnetBlock } from './processor/ProcessorMultiCameraBirdnetBlock';
import { ProcessorConfidenceAdvancedBlock } from './processor/ProcessorConfidenceAdvancedBlock';
import { ProcessorFalsePositiveGuardrailsBlock } from './processor/ProcessorFalsePositiveGuardrailsBlock';
import { ProcessorLightGateBlock } from './processor/ProcessorLightGateBlock';
import { ProcessorSpectrogramDatasetBlock } from './processor/ProcessorSpectrogramDatasetBlock';
import { ProcessorFrigateFusionBlock } from './processor/ProcessorFrigateFusionBlock';
import { ProcessorAdaptiveProfilesBlock } from './processor/ProcessorAdaptiveProfilesBlock';
import { ProcessorDetectorPipelineBlock } from './processor/ProcessorDetectorPipelineBlock';
import { ProcessorBirdnetExtendedBlock } from './processor/ProcessorBirdnetExtendedBlock';
import { ProcessorModelsScopeBlock } from './processor/ProcessorModelsScopeBlock';
import { ProcessorTrackRegenBlock } from './processor/ProcessorTrackRegenBlock';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionProcessor')}
      </AccordionSummary>
      <AccordionDetails>
        <Box
          component="fieldset"
          sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
        >
          <Box
            component="legend"
            sx={{
              clip: 'rect(0,0,0,0)',
              position: 'absolute',
              width: 1,
              height: 1,
              overflow: 'hidden',
            }}
          >
            {t('settings.accordionProcessor')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionProcessorDesc')}
          </Typography>

          <ProcessorConfidenceBlock form={form} />
          <ProcessorSessionTimingBlock form={form} />
          <ProcessorAdaptiveProfilesBlock form={form} />
          <ProcessorDetectorPipelineBlock form={form} />
          <ProcessorMultiCameraBirdnetBlock form={form} />
          <ProcessorBirdnetExtendedBlock form={form} />
          <ProcessorConfidenceAdvancedBlock form={form} />
          <ProcessorFalsePositiveGuardrailsBlock form={form} />
          <ProcessorLightGateBlock form={form} />
          <ProcessorSpectrogramDatasetBlock form={form} />
          <ProcessorModelsScopeBlock form={form} />
          <ProcessorTrackRegenBlock form={form} />
          <ProcessorFrigateFusionBlock form={form} />
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
