import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import { fetchMlRuntimeStatus } from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

const valueOrDash = (value: unknown) =>
  value === null || value === undefined || value === '' ? '—' : String(value);

export function MlRuntimeCard() {
  const { data, isLoading, error } = useQuery({
    queryKey: queryKeys.systemPanels.mlRuntimeStatus,
    queryFn: fetchMlRuntimeStatus,
    staleTime: 30_000,
  });

  if (isLoading) return <LinearProgress />;
  if (error || !data) {
    return (
      <Alert severity="warning" variant="outlined">
        ML runtime status is unavailable.
      </Alert>
    );
  }

  return (
    <SystemCardShell
      title="ML runtime"
      description="Weightless CV/ML rollout status: video capture, detector/classifier backends, detector contract and slow-frame threshold."
      statusLabel={valueOrDash(data.video.capture_backend_config)}
      statusTone="info"
    >
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
        <Chip label={`encoding: ${valueOrDash(data.video.encoding)}`} />
        <Chip
          label={`capture: ${valueOrDash(data.video.capture_backend_config)}`}
        />
        <Chip
          label={`detector backend: ${valueOrDash(data.processor.inference_backend)}`}
        />
        <Chip
          label={`classifier backend: ${valueOrDash(data.processor.classifier_inference_backend)}`}
        />
        <Chip
          label={`contract: ${valueOrDash(
            data.processor.detector_weight_contract,
          )}`}
        />
      </Box>
      <Typography variant="body2" color="text.secondary">
        binary_imgsz={valueOrDash(data.processor.binary_imgsz)} ·
        frame_processing_warn_ms=
        {valueOrDash(data.processor.frame_processing_warn_ms)}
      </Typography>
    </SystemCardShell>
  );
}
