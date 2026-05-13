import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
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
import { ProcessorBehaviorRecognitionBlock } from './processor/ProcessorBehaviorRecognitionBlock';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  simpleMode?: boolean;
};

function SectionHeading({
  children,
  first,
}: {
  children: ReactNode;
  /** Первый подзаголовок сразу после вводного текста — меньше отступ сверху */
  first?: boolean;
}) {
  return (
    <Typography
      variant="overline"
      component="h3"
      sx={{
        display: 'block',
        letterSpacing: 0.08,
        color: 'text.secondary',
        mt: first ? 0.5 : 2.5,
        mb: 1,
        fontWeight: 700,
      }}
    >
      {children}
    </Typography>
  );
}

export function ProcessorSection({ form, simpleMode = true }: Props) {
  const { t } = useTranslation();
  const location = useLocation();
  const expandProcessor =
    location.hash === '#processor-weights' ||
    location.hash === '#processor-models' ||
    location.hash === '#processor-behavior';

  return (
    <Accordion
      defaultExpanded={expandProcessor}
      disableGutters
      sx={{ width: '100%', minWidth: 0, maxWidth: '100%' }}
    >
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionProcessor')}
      </AccordionSummary>
      <AccordionDetails sx={{ minWidth: 0, maxWidth: '100%' }}>
        <Box
          component="fieldset"
          sx={{ border: 'none', p: 0, m: 0, minWidth: 0, maxWidth: '100%' }}
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

          <SectionHeading first>
            {t('settings.processorSectionHeadingDetection')}
          </SectionHeading>
          <ProcessorConfidenceBlock form={form} />
          <ProcessorSessionTimingBlock form={form} />

          <Divider sx={{ my: 2 }} />

          <SectionHeading>
            {t('settings.processorSectionHeadingScene')}
          </SectionHeading>
          <ProcessorLightGateBlock form={form} />
          <ProcessorAdaptiveProfilesBlock form={form} />
          <ProcessorDetectorPipelineBlock form={form} />

          <Divider sx={{ my: 2 }} />

          <SectionHeading>
            {t('settings.processorSectionHeadingBehavior')}
          </SectionHeading>
          <Box id="processor-behavior">
            <ProcessorBehaviorRecognitionBlock form={form} />
          </Box>

          <Divider sx={{ my: 2 }} />

          <SectionHeading>
            {t('settings.processorSectionHeadingAudio')}
          </SectionHeading>
          <ProcessorMultiCameraBirdnetBlock form={form} />
          <ProcessorBirdnetExtendedBlock form={form} />

          <Divider sx={{ my: 2 }} />

          {!simpleMode ? (
            <>
              <SectionHeading>
                {t('settings.processorSectionHeadingQuality')}
              </SectionHeading>
              <ProcessorConfidenceAdvancedBlock form={form} />
              <ProcessorFalsePositiveGuardrailsBlock form={form} />

              <Divider sx={{ my: 2 }} />

              <SectionHeading>
                {t('settings.processorSectionHeadingData')}
              </SectionHeading>
              <ProcessorSpectrogramDatasetBlock form={form} />
              <ProcessorModelsScopeBlock form={form} />
              <ProcessorTrackRegenBlock form={form} />
              <ProcessorFrigateFusionBlock form={form} />
            </>
          ) : null}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
