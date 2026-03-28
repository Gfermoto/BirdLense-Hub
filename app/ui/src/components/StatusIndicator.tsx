import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import VideocamOutlined from '@mui/icons-material/VideocamOutlined';
import CloudOutlined from '@mui/icons-material/CloudOutlined';
import SmartToyOutlined from '@mui/icons-material/SmartToyOutlined';
import PsychologyOutlined from '@mui/icons-material/PsychologyOutlined';
import { useQuery } from '@tanstack/react-query';
import { fetchStatus } from '../api/api';

const STATUS_KEYS: Record<string, Record<string, string>> = {
  video: { ok: 'status.videoOk', unknown: 'status.videoUnknown', offline: 'status.videoUnknown', error: 'status.videoError', not_configured: 'status.videoNotConfigured' },
  mqtt: { ok: 'status.mqttOk', unknown: 'status.mqttUnknown', not_used: 'status.mqttNotUsed', not_configured: 'status.mqttNotConfigured', error: 'status.mqttError', offline: 'status.mqttUnknown' },
  esphome: { ok: 'status.esphomeOk', not_used: 'status.esphomeNotUsed', not_configured: 'status.esphomeNotConfigured', unknown: 'status.esphomeUnknown', error: 'status.esphomeError', offline: 'status.esphomeUnknown' },
  yolo: { ok: 'status.yoloOk', unknown: 'status.yoloUnknown', offline: 'status.yoloUnknown', error: 'status.yoloUnknown' },
};

const StatusDot = ({
  status,
  component,
  icon: Icon,
  t,
}: {
  status: string;
  component: 'video' | 'mqtt' | 'esphome' | 'yolo';
  icon: React.ElementType;
  t: (key: string) => string;
}) => {
  const keys = STATUS_KEYS[component];
  const tipKey = keys?.[status] ?? keys?.unknown ?? `status.${component}Unknown`;
  const tooltip = t(tipKey);

  const color =
    status === 'ok'
      ? 'success.main'
      : status === 'offline' || status === 'error'
        ? '#f87171'
        : status === 'not_used'
          ? 'rgba(255, 255, 255, 0.5)'
          : 'rgba(251, 191, 36, 0.9)';

  return (
    <Tooltip title={tooltip}>
      <Box
        component="span"
        role="img"
        aria-label={tooltip}
        sx={{ display: 'inline-flex', alignItems: 'center', gap: 0.5 }}
      >
        <Icon sx={{ fontSize: 18, color }} aria-hidden />
      </Box>
    </Tooltip>
  );
};

export const StatusIndicator = () => {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ['status'],
    queryFn: fetchStatus,
    refetchInterval: 10000,
  });
  if (!data) return null;
  const trigger = data.trigger_display ?? data.motion_source ?? 'opencv';
  const motion = data.motion_source ?? 'opencv';
  const hintKeys: Record<string, string> = {
    frigate: 'status.motionHint_frigate',
    opencv: 'status.motionHint_opencv',
    mqtt: 'status.motionHint_mqtt',
    esphome: 'status.motionHint_esphome',
  };
  const hint = t(hintKeys[motion] ?? hintKeys.opencv);
  return (
    <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center', flexWrap: 'wrap' }}>
      <StatusDot status={data.video} component="video" icon={VideocamOutlined} t={t} />
      <StatusDot status={data.mqtt} component="mqtt" icon={CloudOutlined} t={t} />
      <StatusDot status={data.esphome ?? 'not_used'} component="esphome" icon={SmartToyOutlined} t={t} />
      <StatusDot status={data.yolo} component="yolo" icon={PsychologyOutlined} t={t} />
      <Tooltip title={hint}>
        <Box component="span" sx={{ fontSize: '0.7rem', color: 'text.secondary' }}>
          {t('status.motion')}: {trigger}
        </Box>
      </Tooltip>
    </Box>
  );
};
