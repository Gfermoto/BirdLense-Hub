import { useTranslation } from 'react-i18next';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Box,
  Card,
  CardContent,
  Chip,
  Divider,
  LinearProgress,
  Typography,
} from '@mui/material';
import { fetchConfigAudit } from '../../api/api';

export function ConfigAuditCard() {
  const { t } = useTranslation();
  const { data, isLoading, error } = useQuery({
    queryKey: ['config-audit'],
    queryFn: fetchConfigAudit,
    staleTime: 30_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) return <Alert severity="warning">{t('system.configAuditLoadError')}</Alert>;

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
            color={data.mapping.gray_to_grey_ok ? 'success' : 'warning'}
            label={data.mapping.gray_to_grey_ok ? t('system.mappingOk') : t('system.mappingNeedsFix')}
          />
          <Chip
            size="small"
            color={data.heimdall.configured ? 'success' : 'default'}
            label={data.heimdall.configured ? t('system.heimdallConfigured') : t('system.heimdallNotConfigured')}
          />
          <Chip
            size="small"
            color={data.gallery.enabled && data.gallery.upload_url ? 'success' : 'default'}
            label={data.gallery.enabled ? t('system.galleryEnabled') : t('system.galleryDisabled')}
          />
          <Chip
            size="small"
            color={data.telegram.send_photo ? 'success' : 'warning'}
            label={data.telegram.send_photo ? t('system.telegramPhotoOn') : t('system.telegramPhotoOff')}
          />
        </Box>

        <Divider sx={{ mb: 1.5 }} />
        <Typography variant="body2" sx={{ mb: 0.5 }}>
          <strong>{t('system.telegramProxyType')}:</strong> {data.telegram.proxy_type}
        </Typography>
        <Typography variant="body2" sx={{ mb: 0.5 }}>
          <strong>{t('system.galleryUrl')}:</strong> {data.gallery.upload_url || '—'}
        </Typography>
        <Typography variant="body2" sx={{ mb: 1.5 }}>
          <strong>{t('system.heimdallUrl')}:</strong> {data.heimdall.url || '—'}
        </Typography>

        {data.deprecated_keys_present.length > 0 && (
          <Alert severity="warning" sx={{ mb: 1 }}>
            {t('system.deprecatedKeysFound', { count: data.deprecated_keys_present.length })}:{' '}
            {data.deprecated_keys_present.join(', ')}
          </Alert>
        )}
        {data.unknown_keys.length > 0 && (
          <Alert severity="info">
            {t('system.unknownKeysFound', { count: data.unknown_keys.length })}:{' '}
            {data.unknown_keys.slice(0, 8).join(', ')}
            {data.unknown_keys.length > 8 ? ' ...' : ''}
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
