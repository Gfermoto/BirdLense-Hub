import Alert from '@mui/material/Alert';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { useQuery } from '@tanstack/react-query';
import {
  fetchDatasetStreamsSummary,
  type DatasetStreamSummary,
} from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

function statusLabel(streams: DatasetStreamSummary[]): string {
  return `${streams.length} streams`;
}

function streamPolicyLabel(stream: DatasetStreamSummary): string {
  if (stream.export_policy.private_backup_only) {
    return 'private backup only';
  }
  if (stream.export_policy.community_export_allowed) {
    return 'community export';
  }
  return 'policy restricted';
}

export function DatasetStreamsCard() {
  const summaryQ = useQuery({
    queryKey: queryKeys.systemPanels.datasetStreamsSummary,
    queryFn: fetchDatasetStreamsSummary,
    staleTime: 60_000,
  });

  if (summaryQ.isLoading) return <LinearProgress />;
  if (summaryQ.error || !summaryQ.data) {
    return (
      <Alert severity="warning" variant="outlined">
        Dataset streams summary is unavailable.
      </Alert>
    );
  }

  const payload = summaryQ.data;
  const streams = payload.streams || [];
  return (
    <SystemCardShell
      id="dataset-streams"
      title="Dataset streams"
      description="Contracts and export policy for detector/classifier/behavior/ReID."
      statusLabel={statusLabel(streams)}
      statusTone={payload.gate.ok ? 'success' : 'warning'}
    >
      <Stack spacing={1.25}>
        <Alert severity={payload.gate.ok ? 'success' : 'warning'} variant="outlined">
          contract gate: {payload.gate.ok ? 'ok' : 'drift detected'}
        </Alert>
        {streams.length === 0 ? (
          <Typography variant="body2" color="text.secondary">
            no stream contracts
          </Typography>
        ) : (
          streams.map((stream) => (
            <Stack key={stream.stream} spacing={0.5}>
              <Stack direction="row" spacing={1} useFlexGap flexWrap="wrap">
                <Chip size="small" label={stream.stream} />
                <Chip
                  size="small"
                  variant="outlined"
                  label={stream.contract_schema || 'schema:unknown'}
                />
                <Chip
                  size="small"
                  variant="outlined"
                  label={streamPolicyLabel(stream)}
                />
              </Stack>
              <Typography variant="caption" color="text.secondary">
                fields: {stream.required_fields_count} | split:{' '}
                {stream.split_required_keys.join(', ') || 'n/a'} | provenance:{' '}
                {stream.provenance_required_keys.join(', ') || 'n/a'}
              </Typography>
            </Stack>
          ))
        )}
      </Stack>
    </SystemCardShell>
  );
}
