import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import Stack from '@mui/material/Stack';
import Button from '@mui/material/Button';
import { SystemMonitor } from './SystemMonitor';
import { ConfigAuditCard } from './ConfigAuditCard';
import { ObservabilityCard } from './ObservabilityCard';
import { CatalogDiagnosticsAccordion } from './CatalogDiagnosticsAccordion';
import { CatalogRepairCard } from './CatalogRepairCard';
import { AutomationCard } from './AutomationCard';
import { AutomationDangerZoneCard } from './AutomationPanels';
import { ProcessorLogs } from './ProcessorLogs';
import { SystemReadinessCard } from './SystemReadinessCard';
import { SystemHero } from './SystemHero';
import { RecognitionImprovementCard } from './RecognitionImprovementCard';
import Box from '@mui/material/Box';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageModeToggle, type PageMode } from '../../components/PageModeToggle';
import { PageSection } from '../../components/PageSection';
import { PageHeader } from '../../components/PageHeader';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { ActionChecklistCard } from '../../components/ActionChecklistCard';

/** Одна колонка карточек: стабильная вёрстка на любых ширинах (без «ломаного» двухколоночного грида). */
const systemStackSx = { minWidth: 0, maxWidth: '100%', width: '100%' } as const;

export const System: React.FC = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.system'));
  const location = useLocation();
  const [mode, setMode] = useState<PageMode>('simple');
  const isAdvanced = mode === 'advanced';

  React.useEffect(() => {
    if (
      location.hash === '#system-workspace' ||
      location.hash === '#system-integrations' ||
      location.hash === '#system-diagnostics' ||
      location.hash === '#system-danger' ||
      location.hash === '#system-danger-zone'
    ) {
      setMode('advanced');
    }
  }, [location.hash]);

  React.useEffect(() => {
    if (!isAdvanced || !location.hash) return;
    const id = location.hash.slice(1);
    const node = document.getElementById(id);
    if (!node) return;
    requestAnimationFrame(() => {
      node.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  }, [isAdvanced, location.hash]);

  return (
    <ProtectedRoute title={t('nav.system')}>
      <Stack spacing={4} sx={{ ...systemStackSx, pb: 1 }}>
        <PageHeader
          title={t('nav.system')}
          description={t('system.pageDescription')}
          actions={
            <PageModeToggle
              value={mode}
              onChange={setMode}
              simpleLabel={t('system.modeOverview')}
              advancedLabel={t('system.modeWorkspace')}
              ariaLabel={t('system.modeAria')}
            />
          }
          titleVariant="h3"
        />

        <SystemHero advanced={isAdvanced} />
        <ActionChecklistCard
          title={t('system.guideTitle')}
          intro={t('system.guideIntro')}
          steps={[
            t('system.guideStep1'),
            t('system.guideStep2'),
            t('system.guideStep3'),
          ]}
          actions={
            <Stack direction="row" flexWrap="wrap" gap={1}>
              <Button href="#system-overview" variant="outlined" size="small">
                {t('system.openHealth')}
              </Button>
              <Button href="#system-integrations" variant="outlined" size="small">
                {t('system.openCatalog')}
              </Button>
              {isAdvanced ? (
                <Button href="#system-workspace" variant="outlined" size="small">
                  {t('system.openWorkspace')}
                </Button>
              ) : null}
            </Stack>
          }
        />

        <Box id="system-overview">
          <PageSection
            title={t('system.sections.overviewTitle')}
            description={t('system.sections.overviewDescription')}
          >
            <Stack spacing={2} sx={systemStackSx}>
              <SystemReadinessCard />
              <SystemMonitor showVisitors={isAdvanced} />
              <RecognitionImprovementCard />
              <ConfigAuditCard simple={!isAdvanced} />
              <ObservabilityCard simple={!isAdvanced} />
            </Stack>
          </PageSection>
        </Box>

        <Box id="system-integrations">
          <PageSection
            title={t('system.sections.catalogTitle')}
            description={t('system.sections.catalogDescription')}
            dividerTop
          >
            <Stack spacing={2} sx={systemStackSx}>
              <CatalogRepairCard />
              {isAdvanced ? <CatalogDiagnosticsAccordion /> : null}
            </Stack>
          </PageSection>
        </Box>

        {isAdvanced ? (
          <Box id="system-workspace">
            <PageSection
              title={t('system.sections.workspaceTitle')}
              description={t('system.sections.workspaceDescription')}
              dividerTop
            >
              <Stack spacing={2} sx={systemStackSx}>
                <AutomationCard />
              </Stack>
            </PageSection>
          </Box>
        ) : null}

        {isAdvanced ? (
          <Box id="system-diagnostics">
            <PageSection
              title={t('system.sections.diagnosticsTitle')}
              description={t('system.sections.diagnosticsDescription')}
              dividerTop
            >
              <ProcessorLogs />
            </PageSection>
          </Box>
        ) : null}

        {isAdvanced ? (
          <Box id="system-danger">
            <PageSection
              title={t('system.sections.dangerTitle')}
              description={t('system.sections.dangerDescription')}
              dividerTop
            >
              <AutomationDangerZoneCard />
            </PageSection>
          </Box>
        ) : null}
      </Stack>
    </ProtectedRoute>
  );
};
