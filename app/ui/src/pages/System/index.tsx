import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import Stack from '@mui/material/Stack';
import { SystemMonitor } from './SystemMonitor';
import { ConfigAuditCard } from './ConfigAuditCard';
import { ObservabilityCard } from './ObservabilityCard';
import { MlRuntimeCard } from './MlRuntimeCard';
import { CatalogDiagnosticsAccordion } from './CatalogDiagnosticsAccordion';
import { CatalogRepairCard } from './CatalogRepairCard';
import { AutomationCard } from './AutomationCard';
import { AutomationDangerZoneCard } from './AutomationPanels';
import { ProcessorLogs } from './ProcessorLogs';
import { SystemReadinessCard } from './SystemReadinessCard';
import { SystemHero } from './SystemHero';
import { RecognitionImprovementCard } from './RecognitionImprovementCard';
import { BehaviorBaselineRetrainCard } from './BehaviorBaselineRetrainCard';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageModeToggle, type PageMode } from '../../components/PageModeToggle';
import { PageSection } from '../../components/PageSection';
import { PageHeader } from '../../components/PageHeader';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
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

  React.useEffect(() => {
    if (location.hash !== '#recognition-improvement') return;
    const node = document.getElementById('recognition-improvement');
    if (!node) return;
    requestAnimationFrame(() => {
      node.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  }, [location.hash]);

  React.useEffect(() => {
    if (location.hash !== '#behavior-baseline-retrain') return;
    const node = document.getElementById('behavior-baseline-retrain');
    if (!node) return;
    requestAnimationFrame(() => {
      node.scrollIntoView({ block: 'start', behavior: 'smooth' });
    });
  }, [location.hash]);

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

        <Alert severity="info" variant="outlined" sx={{ mt: -2 }}>
          {t('system.pageModeToggleHint')}
        </Alert>

        <SystemHero advanced={isAdvanced} />

        <Box id="system-overview">
          <PageSection
            title={t('system.sections.overviewTitle')}
            description={t('system.sections.overviewDescription')}
          >
            <Stack spacing={2} sx={systemStackSx}>
              <SystemReadinessCard />
              <SystemMonitor showVisitors={isAdvanced} />
              <Box
                id="recognition-improvement"
                sx={{ scrollMarginTop: { xs: 1, sm: 2 }, minWidth: 0 }}
              >
                <RecognitionImprovementCard />
              </Box>
              <Box
                id="behavior-baseline-retrain"
                sx={{ scrollMarginTop: { xs: 1, sm: 2 }, minWidth: 0 }}
              >
                <BehaviorBaselineRetrainCard />
              </Box>
              <MlRuntimeCard />
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
