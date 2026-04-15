import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import { Link as RouterLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { PageMessageState } from '../../components/PageState';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

export default function NotFoundPage() {
  const { t } = useTranslation();
  useDocumentTitle(t('common.pageNotFoundTitle'));

  return (
    <PageMessageState
      title={t('common.pageNotFoundTitle')}
      message={t('common.pageNotFoundDescription')}
      action={
        <Stack direction="row" spacing={1}>
          <Button component={RouterLink} to="/" variant="contained">
            {t('common.backToDashboard')}
          </Button>
        </Stack>
      }
      severity="warning"
    />
  );
}
