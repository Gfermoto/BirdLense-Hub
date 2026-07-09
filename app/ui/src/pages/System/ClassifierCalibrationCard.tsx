import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import {
  fetchClassifierCalibrationReport,
  type ClassifierCalibrationReport,
} from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

function pairsLabel(report: ClassifierCalibrationReport): string {
  const n = report.top_confusion_pairs?.length ?? 0;
  return n > 0 ? `${n} pairs` : 'no pairs';
}

export function ClassifierCalibrationCard() {
  const reportQ = useQuery({
    queryKey: queryKeys.systemPanels.classifierCalibrationReport,
    queryFn: () => fetchClassifierCalibrationReport(12),
    staleTime: 60_000,
  });

  if (reportQ.isLoading) return <LinearProgress />;
  if (reportQ.error || !reportQ.data) {
    return (
      <Alert severity="warning" variant="outlined">
        Classifier calibration report is unavailable.
      </Alert>
    );
  }

  const report = reportQ.data;
  const rec = report.threshold_recommendations?.recommended_processor_yaml ?? {};
  const topPairs = report.top_confusion_pairs ?? [];

  return (
    <SystemCardShell
      title="Classifier calibration"
      description="Operator-correction confusion pairs and threshold hints from activity log."
      statusLabel={report.available ? pairsLabel(report) : 'unavailable'}
      statusTone={report.available ? 'info' : 'warning'}
    >
      {!report.available ? (
        <Alert severity="info" variant="outlined" sx={{ mb: 1 }}>
          {report.message ?? 'report unavailable'}
        </Alert>
      ) : null}
      <Stack direction="row" useFlexGap flexWrap="wrap" gap={1} sx={{ mb: 1 }}>
        <Chip
          size="small"
          label={`corrections: ${report.corrections_analyzed ?? 0}`}
        />
        {typeof report.threshold_recommendations?.correction_confidence_p75 ===
        'number' ? (
          <Chip
            size="small"
            label={`corr p75: ${Math.round(
              (report.threshold_recommendations.correction_confidence_p75 ?? 0) *
                100,
            )}%`}
          />
        ) : null}
      </Stack>
      <Box sx={{ mb: 1 }}>
        <Typography variant="caption" color="text.secondary">
          recommended_processor_yaml
        </Typography>
        <Stack direction="row" useFlexGap flexWrap="wrap" gap={1} sx={{ mt: 0.5 }}>
          {Object.entries(rec).length === 0 ? (
            <Typography variant="body2" color="text.secondary">
              no recommendations
            </Typography>
          ) : (
            Object.entries(rec).map(([key, value]) => (
              <Chip key={key} size="small" variant="outlined" label={`${key}: ${value}`} />
            ))
          )}
        </Stack>
      </Box>
      <Typography variant="caption" color="text.secondary">
        Top confusion pairs
      </Typography>
      <Stack spacing={0.5} sx={{ mt: 0.5 }}>
        {topPairs.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            no pairs yet
          </Typography>
        ) : (
          topPairs.slice(0, 5).map((pair, idx) => (
            <Typography key={`${pair.from}-${pair.to}-${idx}`} variant="body2">
              {pair.from} -&gt; {pair.to} ({pair.count})
            </Typography>
          ))
        )}
      </Stack>
    </SystemCardShell>
  );
}
