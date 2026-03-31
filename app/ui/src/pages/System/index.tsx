import React from 'react';
import { useTranslation } from 'react-i18next';
import { SystemMonitor } from './SystemMonitor';
import { ConfigAuditCard } from './ConfigAuditCard';
import { ObservabilityCard } from './ObservabilityCard';
import { CatalogDiagnosticsAccordion } from './CatalogDiagnosticsAccordion';
import { CatalogRepairCard } from './CatalogRepairCard';
import { ProcessorLogs } from './ProcessorLogs';
import { StorageOverview } from './StorageOverview';
import { Box, Divider } from '@mui/material';
import { ProtectedRoute } from '../../components/ProtectedRoute';

export const System: React.FC = () => {
  const { t } = useTranslation();

  return (
    <ProtectedRoute title={t('nav.system')}>
      <Box>
        <Box>
          <SystemMonitor />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <ConfigAuditCard />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <ObservabilityCard />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <CatalogDiagnosticsAccordion />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <CatalogRepairCard />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <StorageOverview />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <ProcessorLogs />
        </Box>
      </Box>
    </ProtectedRoute>
  );
};
