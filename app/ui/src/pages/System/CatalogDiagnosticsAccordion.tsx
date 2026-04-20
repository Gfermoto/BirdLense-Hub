import { useTranslation } from 'react-i18next';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import Typography from '@mui/material/Typography';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import Box from '@mui/material/Box';
import { SpeciesDataQualityCard } from './SpeciesDataQualityCard';
import { ClassifierDatasetAlignmentCard } from './ClassifierDatasetAlignmentCard';

/**
 * Диагностика каталога — свёрнута по умолчанию, чтобы System не выглядел «сырым» для владельца.
 */
export function CatalogDiagnosticsAccordion() {
  const { t } = useTranslation();

  return (
    <Accordion defaultExpanded={false} disableGutters sx={{ minWidth: 0, maxWidth: '100%' }}>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        <Box>
          <Typography variant="subtitle1">{t('system.catalogDiagnosticsTitle')}</Typography>
          <Typography variant="body2" color="text.secondary">
            {t('system.catalogDiagnosticsSummary')}
          </Typography>
        </Box>
      </AccordionSummary>
      <AccordionDetails sx={{ flexDirection: 'column', gap: 3, pt: 0 }}>
        <SpeciesDataQualityCard />
        <ClassifierDatasetAlignmentCard />
      </AccordionDetails>
    </Accordion>
  );
}
