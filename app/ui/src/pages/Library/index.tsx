import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import { useLocation } from 'react-router-dom';
import { ActionChecklistCard } from '../../components/ActionChecklistCard';
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
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export const Library: React.FC = () => {
  const { t } = useTranslation();
  useDocumentTitle(t('nav.library'));
  const location = useLocation();
  const [mode, setMode] = useState<PageMode>('simple');
  const isAdvanced = mode === 'advanced';

  React.useEffect(() => {
    if (location.hash === '#file-replay') {
      setMode('advanced');
    }
  }, [location.hash]);

  return (
    <ProtectedRoute title={t('nav.library')}>
      <Box display="grid" gap={4} sx={{ pb: 5 }}>
        <PageHelp
          {...libraryHelpConfig}
          actions={
            <PageModeToggle
              value={mode}
              onChange={setMode}
              simpleLabel={t('library.modeOverview')}
              advancedLabel={t('library.modeService')}
            />
          }
        />
        <Alert severity="info">{t('library.serviceNotice')}</Alert>
        <ActionChecklistCard
          title={t('library.guideTitle')}
          intro={t('library.guideIntro')}
          steps={[
            t('library.guideStep1'),
            t('library.guideStep2'),
            t('library.guideStep3'),
          ]}
          actions={
            <Stack direction="row" flexWrap="wrap" gap={1}>
              <Button href="#recordings" size="small" variant="outlined">
                {t('library.openArchive')}
              </Button>
              <Button href="#file-replay" size="small" variant="outlined">
                {t('library.openMaintenance')}
              </Button>
            </Stack>
          }
        />
        <PageSection
          title={t('library.sections.archiveTitle')}
          description={t('library.sections.archiveDescription')}
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
        <Box id="file-replay">
          {isAdvanced ? (
            <PageSection
              title={t('library.sections.maintenanceTitle')}
              description={t('library.sections.maintenanceDescription')}
              dividerTop
            >
              <FileReplayCard anchorId="file-replay" />
              <DatabaseMaintenanceCard />
            </PageSection>
          ) : location.hash === '#file-replay' ? (
            <Alert
              severity="info"
              action={
                <Button
                  color="inherit"
                  size="small"
                  onClick={() => setMode('advanced')}
                >
                  {t('common.advancedMode')}
                </Button>
              }
            >
              {t('library.fileReplayAdvancedOnlyHint')}
            </Alert>
          ) : null}
        </Box>
      </Box>
    </ProtectedRoute>
  );
};
