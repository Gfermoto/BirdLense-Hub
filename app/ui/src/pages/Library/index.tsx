import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageHelp } from '../../components/PageHelp';
import { PageModeToggle, type PageMode } from '../../components/PageModeToggle';
import { PageSection } from '../../components/PageSection';
import { libraryHelpConfig } from '../../page-help-config';
import { StorageOverview } from '../System/StorageOverview';
import { DatabaseMaintenanceCard } from '../System/DatabaseMaintenanceCard';
import { RecordingsCalendar } from './RecordingsCalendar';
import { DatasetExportsCard } from './DatasetExportsCard';
import { FileReplayCard } from './FileReplayCard';

export const Library: React.FC = () => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<PageMode>('simple');
  const isAdvanced = mode === 'advanced';

  return (
    <ProtectedRoute title={t('nav.library')}>
      <Box display="grid" gap={4}>
        <PageHelp {...libraryHelpConfig} />
        <PageSection
          title={t('library.sections.archiveTitle')}
          description={t('library.sections.archiveDescription')}
          actions={<PageModeToggle value={mode} onChange={setMode} />}
        >
          <Box id="recordings">
            <RecordingsCalendar />
          </Box>
        </PageSection>
        <PageSection
          title={t('library.sections.exportTitle')}
          description={t('library.sections.exportDescription')}
          dividerTop
        >
          <DatasetExportsCard simple={!isAdvanced} />
        </PageSection>
        <PageSection
          title={t('library.sections.storageTitle')}
          description={t('library.sections.storageDescription')}
          dividerTop
        >
          <StorageOverview simple={!isAdvanced} />
        </PageSection>
        {isAdvanced ? (
          <PageSection
            title={t('library.sections.maintenanceTitle')}
            description={t('library.sections.maintenanceDescription')}
            dividerTop
          >
            <FileReplayCard />
            <DatabaseMaintenanceCard />
          </PageSection>
        ) : null}
      </Box>
    </ProtectedRoute>
  );
};
