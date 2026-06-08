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
import Alert from '@mui/material/Alert';
import type { Settings } from '../../../types';
import { ProcessorConfidenceBlock } from './processor/ProcessorConfidenceBlock';
import { ProcessorSessionTimingBlock } from './processor/ProcessorSessionTimingBlock';
import { ProcessorMultiCameraBirdnetBlock } from './processor/ProcessorMultiCameraBirdnetBlock';
import { ProcessorConfidenceAdvancedBlock } from './processor/ProcessorConfidenceAdvancedBlock';
import { ProcessorFalsePositiveGuardrailsBlock } from './processor/ProcessorFalsePositiveGuardrailsBlock';
import { ProcessorLightGateBlock } from './processor/ProcessorLightGateBlock';
import { ProcessorDatasetBlock } from './processor/ProcessorDatasetBlock';
import { ProcessorFrigateFusionBlock } from './processor/ProcessorFrigateFusionBlock';
import { ProcessorAdaptiveProfilesBlock } from './processor/ProcessorAdaptiveProfilesBlock';
import { ProcessorDetectorPipelineBlock } from './processor/ProcessorDetectorPipelineBlock';
import { ProcessorBirdnetExtendedBlock } from './processor/ProcessorBirdnetExtendedBlock';
import { ProcessorModelsScopeBlock } from './processor/ProcessorModelsScopeBlock';
import { ProcessorTrackRegenBlock } from './processor/ProcessorTrackRegenBlock';
import { ProcessorStreamGeometryBlock } from './processor/ProcessorStreamGeometryBlock';
import { ProcessorOpenVinoBlock } from './processor/ProcessorOpenVinoBlock';
import { ProcessorMotionCalibrationBlock } from './processor/ProcessorMotionCalibrationBlock';
import { ProcessorBehaviorRecognitionBlock } from './processor/ProcessorBehaviorRecognitionBlock';
import { ProcessorDetectFirstBlock } from './processor/ProcessorDetectFirstBlock';
import { ProcessorCameraProfilesBlock } from './processor/ProcessorCameraProfilesBlock';
import { ProcessorRolePresetsBlock } from './processor/ProcessorRolePresetsBlock';

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

          <SectionHeading first>1. Триггеры</SectionHeading>
          <Alert severity="info" variant="outlined" sx={{ mb: 1.5 }}>
            OpenCV/Frigate/motion/scales триггеры настраиваются в разделе «Захват и
            кормушка». Здесь — логика обработки после старта сессии.
          </Alert>
          <ProcessorSessionTimingBlock form={form} />
          {!simpleMode ? <ProcessorFrigateFusionBlock form={form} /> : null}
          <ProcessorLightGateBlock form={form} />
          <ProcessorAdaptiveProfilesBlock form={form} />

          <Divider sx={{ my: 2 }} />

          <SectionHeading>2. Детектор</SectionHeading>
          <ProcessorDetectFirstBlock form={form} />
          <ProcessorDetectorPipelineBlock form={form} />
          <ProcessorStreamGeometryBlock form={form} />
          <ProcessorCameraProfilesBlock form={form} />
          <ProcessorRolePresetsBlock form={form} />
          <ProcessorTrackRegenBlock form={form} />
          {!simpleMode ? (
            <>
              <ProcessorModelsScopeBlock form={form} />
              <ProcessorOpenVinoBlock form={form} />
              <ProcessorMotionCalibrationBlock form={form} />
            </>
          ) : null}

          <Divider sx={{ my: 2 }} />

          <SectionHeading>3. Классификатор и ReID</SectionHeading>
          <ProcessorConfidenceBlock form={form} />
          <ProcessorMultiCameraBirdnetBlock form={form} />
          <ProcessorBirdnetExtendedBlock form={form} />
          {!simpleMode ? (
            <>
              <ProcessorConfidenceAdvancedBlock form={form} />
              <ProcessorFalsePositiveGuardrailsBlock form={form} />
            </>
          ) : null}

          <Divider sx={{ my: 2 }} />

          <SectionHeading>4. Поведение</SectionHeading>
          <Box id="processor-behavior">
            <ProcessorBehaviorRecognitionBlock form={form} />
          </Box>

          {!simpleMode ? (
            <>
              <Divider sx={{ my: 2 }} />
              <SectionHeading>{t('settings.processorSectionHeadingData')}</SectionHeading>
              <ProcessorDatasetBlock form={form} />
            </>
          ) : null}

          {!simpleMode ? (
            <>
              <Divider sx={{ my: 2 }} />
              <SectionHeading>{t('settings.processorSectionHeadingQuality')}</SectionHeading>
              <Typography variant="body2" color="text.secondary">
                Диагностические и quality-gate параметры.
              </Typography>
            </>
          ) : null}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
