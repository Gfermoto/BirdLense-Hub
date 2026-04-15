import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import { fetchConfigAudit } from '../../api/api';

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

  return (
    <Card>
      <CardContent>
        <Typography variant="h6" sx={{ mb: 1.5 }}>
          {t('system.configAuditTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.configAuditHint')}
        </Typography>

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
      </CardContent>
    </Card>
  );
}
