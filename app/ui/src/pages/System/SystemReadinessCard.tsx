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

type GateStatus = 'ok' | 'warn' | 'error';

function normalizeGateStatus(status: string): GateStatus {
  if (status === 'ok' || status === 'warn' || status === 'error') return status;
  return 'error';
}

function statusColor(status: CheckStatus): 'success' | 'error' {
  return status === 'ok' ? 'success' : 'error';
}

function gateBorderColor(
  status: GateStatus,
): 'success.dark' | 'warning.dark' | 'error.dark' {
  if (status === 'ok') return 'success.dark';
  if (status === 'warn') return 'warning.dark';
  return 'error.dark';
}

function gateTextColor(
  status: GateStatus,
): 'success.main' | 'warning.main' | 'error.main' {
  if (status === 'ok') return 'success.main';
  if (status === 'warn') return 'warning.main';
  return 'error.main';
}

function formatRate(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return '—';
  return `${(value * 100).toFixed(1)}%`;
}

export function SystemReadinessCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useSystemReadinessQuery();

  if (isLoading) return <LinearProgress />;
  if (error || !data)
    return (
      <Alert severity="warning" variant="outlined">
        {t('system.readinessLoadError')}
      </Alert>
    );

  const checks = [
    ['database', normalizeCheckStatus(data.checks.database?.status ?? '')],
    ['dataDir', normalizeCheckStatus(data.checks.data_dir?.status ?? '')],
    [
      'configDir',
      normalizeCheckStatus(data.checks.app_config_dir?.status ?? ''),
    ],
    ['web', normalizeCheckStatus(data.components.web ?? '')],
  ] as const;

  const sg = data.security_gates;
  const gateItems = sg?.items ?? [];
  const runtimeLabel = sg?.runtime
    ? t(`system.readinessRuntime.${sg.runtime}`)
    : '';

  const funnelCheck = data.checks.pipeline_funnel;
  const funnel = data.pipeline_funnel;
  const funnelStatus = String(funnelCheck?.status ?? funnel?.status ?? 'unknown');
  const funnelDegraded = funnelStatus === 'degraded';
  const topCauses = funnel?.top_root_causes ?? funnelCheck?.top_root_causes ?? [];
  const funnelAlerts = funnel?.alerts ?? funnelCheck?.alerts ?? [];
  const byCamera = funnel?.by_camera ?? {};
  const cameraIds = Object.keys(byCamera);

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

        {funnel ? (
          <Stack spacing={1}>
            <Typography variant="subtitle2">
              {t('system.readinessFunnelTitle')}
            </Typography>
            <Typography variant="caption" color="text.secondary">
              {t('system.readinessFunnelHint', {
                hours: funnel.window_hours ?? 24,
              })}
            </Typography>
            <Box
              sx={{
                p: 1.25,
                borderRadius: 2,
                bgcolor: 'background.default',
                border: '1px solid',
                borderColor: funnelDegraded ? 'warning.dark' : 'success.dark',
              }}
            >
              <Typography variant="caption" color="text.secondary" display="block">
                {t('system.readinessFunnelStatus')}
              </Typography>
              <Typography
                variant="subtitle2"
                color={funnelDegraded ? 'warning.main' : 'success.main'}
                sx={{ mt: 0.5 }}
              >
                {t(`system.readinessFunnelState.${funnelStatus}`, {
                  defaultValue: funnelStatus,
                })}
              </Typography>
              <Typography variant="body2" sx={{ mt: 1 }}>
                {t('system.readinessFunnelSessions', {
                  total: funnel.sessions_total ?? 0,
                  healthy: formatRate(funnel.healthy_persist_rate),
                  fusionDrop: formatRate(funnel.fusion_drop_rate),
                })}
              </Typography>
            </Box>
            {topCauses.length > 0 ? (
              <Stack spacing={0.5}>
                <Typography variant="caption" color="text.secondary">
                  {t('system.readinessFunnelTopCauses')}
                </Typography>
                {topCauses.map((mode) => (
                  <Typography key={mode} variant="body2">
                    {t(`system.readinessFunnelFailureMode.${mode}`, {
                      defaultValue: mode,
                    })}
                  </Typography>
                ))}
              </Stack>
            ) : null}
            {funnelAlerts.length > 0 ? (
              <Alert severity="warning" variant="outlined">
                {funnelAlerts.map((alert) => (
                  <Typography key={alert} variant="body2">
                    {alert}
                  </Typography>
                ))}
              </Alert>
            ) : null}
            {cameraIds.length > 0 ? (
              <Stack spacing={0.75}>
                <Typography variant="caption" color="text.secondary">
                  {t('system.readinessFunnelByCamera')}
                </Typography>
                {cameraIds.map((cameraId) => {
                  const modes = byCamera[cameraId] ?? {};
                  const dominant = Object.entries(modes).sort(
                    (a, b) => b[1] - a[1],
                  )[0];
                  if (!dominant) return null;
                  const [mode, count] = dominant;
                  return (
                    <Typography key={cameraId} variant="body2">
                      {cameraId}:{' '}
                      {t(`system.readinessFunnelFailureMode.${mode}`, {
                        defaultValue: mode,
                      })}{' '}
                      ({count})
                    </Typography>
                  );
                })}
              </Stack>
            ) : null}
          </Stack>
        ) : null}

        {gateItems.length > 0 ? (
          <Stack spacing={1}>
            <Typography variant="subtitle2">
              {t('system.readinessSecurityTitle')}
            </Typography>
            {runtimeLabel ? (
              <Typography variant="caption" color="text.secondary">
                {t('system.readinessSecurityRuntime', {
                  runtime: runtimeLabel,
                })}
              </Typography>
            ) : null}
            <Box
              sx={{
                display: 'grid',
                gap: 1,
                gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
              }}
            >
              {gateItems.map((item) => {
                const st = normalizeGateStatus(item.status);
                return (
                  <Box
                    key={item.id}
                    sx={{
                      p: 1.25,
                      borderRadius: 2,
                      bgcolor: 'background.default',
                      border: '1px solid',
                      borderColor: gateBorderColor(st),
                    }}
                  >
                    <Typography
                      variant="caption"
                      color="text.secondary"
                      display="block"
                    >
                      {t(`system.readinessCheck.${item.id}`)}
                    </Typography>
                    <Typography
                      variant="subtitle2"
                      color={gateTextColor(st)}
                      sx={{ mt: 0.5 }}
                    >
                      {t(`system.readinessState.${st}`)}
                    </Typography>
                  </Box>
                );
              })}
            </Box>
          </Stack>
        ) : null}

        <Alert severity={data.ready ? 'success' : 'warning'} variant="outlined">
          {data.ready
            ? t('system.readinessVerifyPass')
            : t('system.readinessVerifyFail')}
        </Alert>
      </Stack>
    </SystemCardShell>
  );
}
