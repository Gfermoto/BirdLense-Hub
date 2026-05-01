import { useQuery } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Typography from '@mui/material/Typography';
import {
  fetchFeedbackLoopStatus,
  fetchMlRuntimeStatus,
} from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

const valueOrDash = (value: unknown) =>
  value === null || value === undefined || value === '' ? '—' : String(value);

export function MlRuntimeCard() {
  const runtime = useQuery({
    queryKey: queryKeys.systemPanels.mlRuntimeStatus,
    queryFn: fetchMlRuntimeStatus,
    staleTime: 30_000,
  });
  const feedback = useQuery({
    queryKey: queryKeys.systemPanels.feedbackLoopStatus,
    queryFn: fetchFeedbackLoopStatus,
    staleTime: 30_000,
  });

  if (runtime.isLoading) return <LinearProgress />;
  if (runtime.error || !runtime.data) {
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
      statusLabel={valueOrDash(runtime.data.video.capture_backend_config)}
      statusTone="info"
    >
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 1 }}>
        <Chip label={`encoding: ${valueOrDash(runtime.data.video.encoding)}`} />
        <Chip
          label={`capture: ${valueOrDash(runtime.data.video.capture_backend_config)}`}
        />
        <Chip
          label={`detector backend: ${valueOrDash(runtime.data.processor.inference_backend)}`}
        />
        <Chip
          label={`classifier backend: ${valueOrDash(runtime.data.processor.classifier_inference_backend)}`}
        />
        <Chip
          label={`contract: ${valueOrDash(
            runtime.data.processor.detector_weight_contract,
          )}`}
        />
        {feedback.data && (
          <Chip
            color="secondary"
            label={`feedback events: ${valueOrDash(feedback.data.events_total)}`}
          />
        )}
      </Box>
      <Typography variant="body2" color="text.secondary">
        binary_imgsz={valueOrDash(runtime.data.processor.binary_imgsz)} ·
        frame_processing_warn_ms=
        {valueOrDash(runtime.data.processor.frame_processing_warn_ms)}
      </Typography>
      {feedback.data?.latest_export && (
        <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
          feedback export: {valueOrDash(feedback.data.latest_export.status)} · exported=
          {valueOrDash(feedback.data.latest_export.exported_total)} · missing=
          {valueOrDash(feedback.data.latest_export.missing_crop_events)}
        </Typography>
      )}
    </SystemCardShell>
  );
}
