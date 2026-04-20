import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useTranslation } from 'react-i18next';
import { useSystemReadinessQuery } from '../../hooks/useSystemQueries';
import { SystemCardShell } from './SystemCardShell';

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
  if (error || !data)
    return <Alert severity="warning">{t('system.readinessLoadError')}</Alert>;

  const checks = [
    ['database', normalizeCheckStatus(data.checks.database.status)],
    ['dataDir', normalizeCheckStatus(data.checks.data_dir.status)],
    ['configDir', normalizeCheckStatus(data.checks.app_config_dir.status)],
    ['web', normalizeCheckStatus(data.components.web)],
  ] as const;

  return (
    <SystemCardShell
      title={t('system.readinessTitle')}
      description={t('system.readinessHint')}
      statusLabel={
        data.ready ? t('system.readinessReady') : t('system.readinessDegraded')
      }
      statusTone={data.ready ? 'success' : 'warning'}
      footer={
        <Typography variant="body2" color="text.secondary">
          {t('system.readinessCheckedAt', { at: data.checked_at })}
        </Typography>
      }
    >
      <Stack spacing={2}>
        <Box
          sx={{
            display: 'grid',
            gap: 1,
            gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
          }}
        >
          {checks.map(([key, status]) => (
            <Box
              key={key}
              sx={{
                p: 1.25,
                borderRadius: 2,
                bgcolor: 'background.default',
                border: '1px solid',
                borderColor: status === 'ok' ? 'success.dark' : 'error.dark',
              }}
            >
              <Typography
                variant="caption"
                color="text.secondary"
                display="block"
              >
                {t(`system.readinessCheck.${key}`)}
              </Typography>
              <Typography
                variant="subtitle2"
                color={
                  statusColor(status) === 'success'
                    ? 'success.main'
                    : 'error.main'
                }
                sx={{ mt: 0.5 }}
              >
                {t(`system.readinessState.${status}`)}
              </Typography>
            </Box>
          ))}
        </Box>

        <Alert severity={data.ready ? 'success' : 'warning'}>
          {data.ready
            ? t('system.readinessVerifyPass')
            : t('system.readinessVerifyFail')}
        </Alert>
      </Stack>
    </SystemCardShell>
  );
}
