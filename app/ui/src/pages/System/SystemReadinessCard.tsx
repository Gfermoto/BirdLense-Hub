import Alert from '@mui/material/Alert';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { useSystemReadinessQuery } from '../../hooks/useSystemQueries';

type CheckStatus = 'ok' | 'error';

function normalizeCheckStatus(status: string): CheckStatus {
  return status === 'ok' ? 'ok' : 'error';
}

function statusColor(status: CheckStatus): 'success' | 'error' {
  return status === 'ok' ? 'success' : 'error';
}

export function SystemReadinessCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useSystemReadinessQuery();

  if (isLoading) return <LinearProgress />;
  if (error || !data) return <Alert severity="warning">{t('system.readinessLoadError')}</Alert>;

  const checks = [
    ['database', normalizeCheckStatus(data.checks.database.status)],
    ['dataDir', normalizeCheckStatus(data.checks.data_dir.status)],
    ['configDir', normalizeCheckStatus(data.checks.app_config_dir.status)],
    ['web', normalizeCheckStatus(data.components.web)],
  ] as const;

  return (
    <Card>
      <CardContent>
        <Stack spacing={2}>
          <div>
            <Typography variant="h6">{t('system.readinessTitle')}</Typography>
            <Typography variant="body2" color="text.secondary">
              {t('system.readinessHint')}
            </Typography>
          </div>

          <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
            <Chip
              color={data.ready ? 'success' : 'warning'}
              label={data.ready ? t('system.readinessReady') : t('system.readinessDegraded')}
            />
            {checks.map(([key, status]) => (
              <Chip
                key={key}
                size="small"
                variant="outlined"
                color={statusColor(status)}
                label={`${t(`system.readinessCheck.${key}`)}: ${t(`system.readinessState.${status}`)}`}
              />
            ))}
          </Stack>

          <Typography variant="body2" color="text.secondary">
            {t('system.readinessCheckedAt', { at: data.checked_at })}
          </Typography>

          <Alert severity={data.ready ? 'success' : 'warning'}>
            {data.ready ? t('system.readinessVerifyPass') : t('system.readinessVerifyFail')}
          </Alert>
        </Stack>
      </CardContent>
    </Card>
  );
}
