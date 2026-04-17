import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import LinearProgress from '@mui/material/LinearProgress';
import List from '@mui/material/List';
import ListItem from '@mui/material/ListItem';
import ListItemText from '@mui/material/ListItemText';
import Typography from '@mui/material/Typography';
import { fetchConfigAudit } from '../../api/api';
import { SystemCardShell } from './SystemCardShell';

export function ConfigAuditCard({
  simple = false,
}: {
  simple?: boolean;
}) {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-audit'],
    queryFn: fetchConfigAudit,
    staleTime: 30_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) return <Alert severity="warning">{t('system.configAuditLoadError')}</Alert>;
  const mappingOk = data.mapping?.gray_to_grey_ok ?? false;
  const telegramPhoto = data.telegram?.send_photo ?? false;
  const deprecatedKeys = Array.isArray(data.deprecated_keys_present) ? data.deprecated_keys_present : [];
  const unknownKeys = Array.isArray(data.unknown_keys) ? data.unknown_keys : [];
  const configWarnings = Array.isArray(data.config_warnings) ? data.config_warnings : [];
  const configHints = Array.isArray(data.config_hints) ? data.config_hints : [];
  const sm = data.scales_mqtt as Record<string, unknown> | undefined;
  const statusTone =
    configWarnings.length > 0 || deprecatedKeys.length > 0 ? 'warning' : 'success';

  return (
    <SystemCardShell
      title={t('system.configAuditTitle')}
      description={t('system.configAuditHint')}
      statusLabel={
        configWarnings.length > 0 || deprecatedKeys.length > 0
          ? t('system.configAuditNeedsReview')
          : t('system.readinessReady')
      }
      statusTone={statusTone}
    >
      <Box>
        {sm?.enabled === true && (
          <Box sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {t('system.configAuditScalesSection')}
            </Typography>
            <Typography variant="body2" component="div" sx={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>
              {t('system.configAuditScalesSource')}: {String(sm.source ?? '—')}
              {' · '}
              {t('system.configAuditScalesBroker')}:{' '}
              {sm.mqtt_broker_configured === true ? t('system.configAuditYes') : t('system.configAuditNo')}
            </Typography>
            {typeof sm.mqtt_weight_topic_resolved === 'string' && sm.mqtt_weight_topic_resolved ? (
              <Typography variant="body2" sx={{ mt: 0.5, fontFamily: 'monospace', fontSize: '0.8rem' }}>
                {t('system.configAuditScalesWeightTopic')}: {sm.mqtt_weight_topic_resolved}
              </Typography>
            ) : null}
            {sm.mqtt_note === 'esphome_or_ha' ? (
              <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 0.5 }}>
                {t('system.configAuditScalesNotMqtt')}
              </Typography>
            ) : null}
          </Box>
        )}

        {configWarnings.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {t('system.configAuditWarningsTitle')}
            </Typography>
            <List dense disablePadding sx={{ listStyleType: 'disc', pl: 2 }}>
              {configWarnings.map((w, i) => (
                <ListItem key={i} disableGutters sx={{ display: 'list-item', py: 0.25 }}>
                  <ListItemText primaryTypographyProps={{ variant: 'body2' }} primary={w} />
                </ListItem>
              ))}
            </List>
          </Alert>
        )}

        {configHints.length > 0 && (
          <Alert severity="info" sx={{ mb: 2 }}>
            <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
              {t('system.configAuditHintsTitle')}
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 0.75 }}>
              {t('system.configAuditHintsHint')}
            </Typography>
            <List dense disablePadding sx={{ listStyleType: 'disc', pl: 2 }}>
              {configHints.map((h, i) => (
                <ListItem key={i} disableGutters sx={{ display: 'list-item', py: 0.25 }}>
                  <ListItemText primaryTypographyProps={{ variant: 'body2' }} primary={h} />
                </ListItem>
              ))}
            </List>
          </Alert>
        )}

        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
          <Chip
            size="small"
            color={mappingOk ? 'success' : 'warning'}
            label={mappingOk ? t('system.mappingOk') : t('system.mappingNeedsFix')}
          />
          <Chip
            size="small"
            color={telegramPhoto ? 'success' : 'warning'}
            label={telegramPhoto ? t('system.telegramPhotoOn') : t('system.telegramPhotoOff')}
          />
        </Box>

        {!simple ? <Divider sx={{ mb: 1.5 }} /> : null}
        {!simple ? (
          <>
            <Typography variant="body2" sx={{ mb: 0.5 }}>
              <strong>{t('system.telegramProxyType')}:</strong> {data.telegram?.proxy_type || '—'}
            </Typography>
          </>
        ) : null}

        {deprecatedKeys.length > 0 && (
          <Alert severity="warning" sx={{ mb: 1 }}>
            {t('system.deprecatedKeysFound', { count: deprecatedKeys.length })}:{' '}
            {deprecatedKeys.join(', ')}
          </Alert>
        )}
        {!simple && unknownKeys.length > 0 && (
          <Alert severity="info">
            {t('system.unknownKeysFound', { count: unknownKeys.length })}:{' '}
            {unknownKeys.slice(0, 8).join(', ')}
            {unknownKeys.length > 8 ? ' ...' : ''}
          </Alert>
        )}
      </Box>
    </SystemCardShell>
  );
}
