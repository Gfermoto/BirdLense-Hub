import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { SystemMonitor } from './SystemMonitor';
import { ConfigAuditCard } from './ConfigAuditCard';
import { ObservabilityCard } from './ObservabilityCard';
import { CatalogDiagnosticsAccordion } from './CatalogDiagnosticsAccordion';
import { CatalogRepairCard } from './CatalogRepairCard';
import { AutomationCard } from './AutomationCard';
import { AutomationDangerZoneCard } from './AutomationPanels';
import { ProcessorLogs } from './ProcessorLogs';
import { ProcessorWeightsCard } from './ProcessorWeightsCard';
import { SystemReadinessCard } from './SystemReadinessCard';
import { SystemHero } from './SystemHero';
import Box from '@mui/material/Box';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageModeToggle, type PageMode } from '../../components/PageModeToggle';
import { PageSection } from '../../components/PageSection';
import { PageHeader } from '../../components/PageHeader';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export const System: React.FC = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.system'));
  const location = useLocation();
  const [mode, setMode] = useState<PageMode>('simple');
  const isAdvanced = mode === 'advanced';

  React.useEffect(() => {
    if (
      location.hash === '#system-workspace' ||
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
      <Box display="grid" gap={4}>
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

        <Box id="system-overview">
          <PageSection
            title={t('system.sections.overviewTitle')}
            description={t('system.sections.overviewDescription')}
          >
            <Box
              sx={{
                display: 'grid',
                gap: 2,
                gridTemplateColumns: { xs: '1fr', xl: 'minmax(0, 0.95fr) minmax(320px, 0.75fr)' },
                alignItems: 'start',
              }}
            >
              <Box display="grid" gap={2}>
                <SystemReadinessCard />
                <SystemMonitor showVisitors={isAdvanced} />
              </Box>
              <Box display="grid" gap={2}>
                <ConfigAuditCard simple={!isAdvanced} />
                <ObservabilityCard simple={!isAdvanced} />
              </Box>
            </Box>
          </PageSection>
        </Box>

        <Box id="system-integrations">
          <PageSection
            title={t('system.sections.catalogTitle')}
            description={t('system.sections.catalogDescription')}
            dividerTop
          >
            <Box
              sx={{
                display: 'grid',
                gap: 2,
                gridTemplateColumns: { xs: '1fr', xl: 'minmax(0, 0.9fr) minmax(320px, 0.9fr)' },
              }}
            >
              <CatalogRepairCard />
              {isAdvanced ? <CatalogDiagnosticsAccordion /> : null}
            </Box>
          </PageSection>
        </Box>

        {isAdvanced ? (
          <Box id="system-workspace">
            <PageSection
              title={t('system.sections.workspaceTitle')}
              description={t('system.sections.workspaceDescription')}
              dividerTop
            >
              <Box
                sx={{
                  display: 'grid',
                  gap: 2,
                  gridTemplateColumns: { xs: '1fr', xl: 'minmax(0, 0.9fr) minmax(0, 1.1fr)' },
                  alignItems: 'start',
                }}
              >
                <ProcessorWeightsCard />
                <AutomationCard />
              </Box>
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
      </Box>
    </ProtectedRoute>
  );
};
