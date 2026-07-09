import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import { Link as RouterLink } from 'react-router-dom';

export function ProcessorOpencvMaskHint() {
  const { t } = useTranslation();
  return (
    <Alert severity="info" variant="outlined" sx={{ mb: 1.5 }}>
      {t('settings.opencvMasksLiveHint')}{' '}
      <Button
        component={RouterLink}
        to="/live"
        size="small"
        variant="outlined"
        sx={{ ml: 0.5, verticalAlign: 'baseline' }}
      >
        {t('settings.opencvMasksLiveLink')}
      </Button>
    </Alert>
  );
}
