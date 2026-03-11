import React from 'react';
import { useTranslation } from 'react-i18next';
import { SystemActivity } from './SystemActivity';
import { SystemMonitor } from './SystemMonitor';
import { Box, Divider } from '@mui/material';
import { StorageManagement } from './StorageManagement';
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
          <SystemActivity />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <StorageManagement />
        </Box>
      </Box>
    </ProtectedRoute>
  );
};
