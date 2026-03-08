import Box from '@mui/material/Box';
import Tooltip from '@mui/material/Tooltip';
import VideocamOutlined from '@mui/icons-material/VideocamOutlined';
import CloudOutlined from '@mui/icons-material/CloudOutlined';
import SmartToyOutlined from '@mui/icons-material/SmartToyOutlined';
import PsychologyOutlined from '@mui/icons-material/PsychologyOutlined';
import { useQuery } from '@tanstack/react-query';
import { fetchStatus } from '../api/api';

const StatusDot = ({
  status,
  label,
  icon: Icon,
}: {
  status: string;
  label: string;
  icon: React.ElementType;
}) => {
  const color =
    status === 'ok'
      ? 'success.main'
      : status === 'offline' || status === 'error'
        ? 'error.main'
        : 'grey.500';
  return (
    <Tooltip title={`${label}: ${status}`}>
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
        <Icon sx={{ fontSize: 18, color }} />
      </Box>
    </Tooltip>
  );
};

export const StatusIndicator = () => {
  const { data } = useQuery({
    queryKey: ['status'],
    queryFn: fetchStatus,
    refetchInterval: 30000,
  });
  if (!data) return null;
  return (
    <Box sx={{ display: 'flex', gap: 1.5, alignItems: 'center' }}>
      <StatusDot status={data.video} label="Video" icon={VideocamOutlined} />
      <StatusDot status={data.mqtt} label="MQTT" icon={CloudOutlined} />
      <StatusDot status={data.esphome ?? 'not_used'} label="ESPHome" icon={SmartToyOutlined} />
      <StatusDot status={data.yolo} label="YOLO" icon={PsychologyOutlined} />
    </Box>
  );
};
