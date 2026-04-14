import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { SystemMonitor } from './SystemMonitor';
import { ConfigAuditCard } from './ConfigAuditCard';
import { ObservabilityCard } from './ObservabilityCard';
import { CatalogDiagnosticsAccordion } from './CatalogDiagnosticsAccordion';
import { CatalogRepairCard } from './CatalogRepairCard';
import { AutomationCard } from './AutomationCard';
import { ProcessorLogs } from './ProcessorLogs';
import { ProcessorWeightsCard } from './ProcessorWeightsCard';
import Box from '@mui/material/Box';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageModeToggle, type PageMode } from '../../components/PageModeToggle';
import { PageSection } from '../../components/PageSection';

export const System: React.FC = () => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<PageMode>('simple');
  const isAdvanced = mode === 'advanced';

  return (
    <ProtectedRoute title={t('nav.system')}>
      <Box display="grid" gap={4}>
        <PageSection
          title={t('system.sections.healthTitle')}
          description={t('system.sections.healthDescription')}
          actions={<PageModeToggle value={mode} onChange={setMode} />}
        >
          <SystemMonitor showVisitors={isAdvanced} />
        </PageSection>

        <PageSection
          title={t('system.sections.integrationsTitle')}
          description={t('system.sections.integrationsDescription')}
          dividerTop
        >
          <ConfigAuditCard simple={!isAdvanced} />
          <ObservabilityCard simple={!isAdvanced} />
        </PageSection>

        <PageSection
          title={t('system.sections.catalogTitle')}
          description={t('system.sections.catalogDescription')}
          dividerTop
        >
          <CatalogRepairCard />
          {isAdvanced ? <CatalogDiagnosticsAccordion /> : null}
        </PageSection>

        {isAdvanced ? (
          <PageSection
            title={t('system.sections.processingTitle')}
            description={t('system.sections.processingDescription')}
            dividerTop
          >
            <ProcessorWeightsCard />
            <AutomationCard />
          </PageSection>
        ) : null}

        {isAdvanced ? (
          <PageSection
            title={t('system.sections.diagnosticsTitle')}
            description={t('system.sections.diagnosticsDescription')}
            dividerTop
          >
            <ProcessorLogs />
          </PageSection>
        ) : null}
      </Box>
    </ProtectedRoute>
  );
};
