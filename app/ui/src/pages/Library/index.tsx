import React from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageHelp } from '../../components/PageHelp';
import { libraryHelpConfig } from '../../page-help-config';
import { StorageOverview } from '../System/StorageOverview';
import { DatabaseMaintenanceCard } from '../System/DatabaseMaintenanceCard';
import { RecordingsCalendar } from './RecordingsCalendar';
import { DatasetExportsCard } from './DatasetExportsCard';

export const Library: React.FC = () => {
  const { t } = useTranslation();

  return (
    <ProtectedRoute title={t('nav.library')} requireAdmin={false}>
      <Box display="grid" gap={2}>
        <PageHelp {...libraryHelpConfig} />
        <Box id="recordings">
          <RecordingsCalendar />
        </Box>
        <DatasetExportsCard />
        <DatabaseMaintenanceCard />
        <StorageOverview />
      </Box>
    </ProtectedRoute>
  );
};
