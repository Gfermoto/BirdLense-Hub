import React from 'react';
import { useTranslation } from 'react-i18next';
import { SystemActivity } from '../System/SystemActivity';
import { RecordingsAndDataset } from './RecordingsAndDataset';
import { Box, Divider } from '@mui/material';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import { PageHelp } from '../../components/PageHelp';
import { libraryHelpConfig } from '../../page-help-config';

export const Library: React.FC = () => {
  const { t } = useTranslation();

  return (
    <ProtectedRoute title={t('nav.library')}>
      <Box>
        <PageHelp {...libraryHelpConfig} />
        <Box>
          <SystemActivity />
        </Box>

        <Divider sx={{ my: 3 }} />

        <Box>
          <RecordingsAndDataset />
        </Box>
      </Box>
    </ProtectedRoute>
  );
};
