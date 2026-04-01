import React from 'react';
import { useTranslation } from 'react-i18next';
import { SystemMonitor } from './SystemMonitor';
import { ConfigAuditCard } from './ConfigAuditCard';
import { ObservabilityCard } from './ObservabilityCard';
import { CatalogDiagnosticsAccordion } from './CatalogDiagnosticsAccordion';
import { CatalogRepairCard } from './CatalogRepairCard';
<<<<<<< HEAD
import { DatabaseMaintenanceCard } from './DatabaseMaintenanceCard';
=======
>>>>>>> 33e94c3bb0988b2cc797724d9cdef283f7d5b816
import { ProcessorLogs } from './ProcessorLogs';
import { StorageOverview } from './StorageOverview';
import Box from '@mui/material/Box';
import Divider from '@mui/material/Divider';
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
<<<<<<< HEAD
          <DatabaseMaintenanceCard />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
=======
>>>>>>> 33e94c3bb0988b2cc797724d9cdef283f7d5b816
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
