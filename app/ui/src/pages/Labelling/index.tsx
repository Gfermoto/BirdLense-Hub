import React from 'react';
import {
  Alert,
  Box,
  Button,
  Card,
  CardContent,
  Chip,
  FormControl,
  InputLabel,
  MenuItem,
  Select,
  Stack,
  Typography,
} from '@mui/material';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';
import { PageHeader } from '../../components/PageHeader';
import { ProtectedRoute } from '../../components/ProtectedRoute';
import {
  useExportLabellingCasesMutation,
  useLabellingCasesQuery,
  useMineLabellingCasesMutation,
  usePatchLabellingCaseMutation,
} from '../../hooks/useLabellingQueries';
import type { LabellingCaseStatus } from '../../api/labelling';

type FilterStatus = LabellingCaseStatus | 'all';

const statusColor: Record<LabellingCaseStatus, 'default' | 'success' | 'error' | 'warning'> = {
  pending: 'warning',
  approved: 'success',
  rejected: 'error',
};

export const LabellingPage: React.FC = () => {
  useDocumentTitle('Labelling');
  const [status, setStatus] = React.useState<FilterStatus>('pending');
  const [exportFormat, setExportFormat] = React.useState<'yolo' | 'coco'>('yolo');
  const q = useLabellingCasesQuery(status, 150);
  const mine = useMineLabellingCasesMutation();
  const patch = usePatchLabellingCaseMutation();
  const exp = useExportLabellingCasesMutation();

  return (
    <ProtectedRoute title="Labelling" requireAdmin={false}>
      <Stack spacing={2}>
        <PageHeader
          title="Active Learning / Labelling"
          description="Hard cases queue: blind-score, fallback ratio, borderline confidence."
          titleVariant="h4"
        />
        <Card>
          <CardContent>
            <Stack direction={{ xs: 'column', md: 'row' }} spacing={1.5} alignItems={{ md: 'center' }}>
              <Button
                variant="contained"
                onClick={() => mine.mutate({ lookback_hours: 72, max_rows: 500 })}
                disabled={mine.isPending}
              >
                Run Hard-Case Miner
              </Button>
              <FormControl size="small" sx={{ minWidth: 180 }}>
                <InputLabel id="labelling-status-label">Status</InputLabel>
                <Select
                  labelId="labelling-status-label"
                  value={status}
                  label="Status"
                  onChange={(e) => setStatus(e.target.value as FilterStatus)}
                >
                  <MenuItem value="all">all</MenuItem>
                  <MenuItem value="pending">pending</MenuItem>
                  <MenuItem value="approved">approved</MenuItem>
                  <MenuItem value="rejected">rejected</MenuItem>
                </Select>
              </FormControl>
              <FormControl size="small" sx={{ minWidth: 150 }}>
                <InputLabel id="labelling-export-label">Export</InputLabel>
                <Select
                  labelId="labelling-export-label"
                  value={exportFormat}
                  label="Export"
                  onChange={(e) => setExportFormat(e.target.value as 'yolo' | 'coco')}
                >
                  <MenuItem value="yolo">YOLO</MenuItem>
                  <MenuItem value="coco">COCO</MenuItem>
                </Select>
              </FormControl>
              <Button
                variant="outlined"
                onClick={() => exp.mutate({ format: exportFormat, status: 'approved' })}
                disabled={exp.isPending}
              >
                Export approved
              </Button>
            </Stack>
            {mine.data ? (
              <Alert sx={{ mt: 1.5 }} severity="info">
                Miner: created {mine.data.created}, skipped {mine.data.skipped}
              </Alert>
            ) : null}
            {exp.data ? (
              <Alert sx={{ mt: 1.5 }} severity="success">
                Export done: {exp.data.format} {exp.data.version} ({exp.data.path})
              </Alert>
            ) : null}
          </CardContent>
        </Card>
        <Stack spacing={1.5}>
          {(q.data?.items || []).map((item) => (
            <Card key={item.id}>
              <CardContent>
                <Stack spacing={1}>
                  <Stack direction="row" spacing={1} alignItems="center" flexWrap="wrap">
                    <Typography variant="subtitle1">Case #{item.id}</Typography>
                    <Chip size="small" label={item.status} color={statusColor[item.status]} />
                    <Chip size="small" label={item.reason_code} />
                    {item.species_name ? <Chip size="small" label={item.species_name} variant="outlined" /> : null}
                  </Stack>
                  <Typography variant="body2" color="text.secondary">
                    conf={item.confidence ?? '-'} blind_score={item.blind_score ?? '-'} fallback_ratio=
                    {item.fallback_ratio ?? '-'} camera={item.camera_id ?? '-'}
                  </Typography>
                  <Box>
                    <Button
                      size="small"
                      onClick={() => patch.mutate({ id: item.id, status: 'approved' })}
                      disabled={patch.isPending}
                    >
                      Approve
                    </Button>
                    <Button
                      size="small"
                      onClick={() => patch.mutate({ id: item.id, status: 'rejected' })}
                      disabled={patch.isPending}
                    >
                      Reject
                    </Button>
                    <Button
                      size="small"
                      onClick={() => patch.mutate({ id: item.id, status: 'pending' })}
                      disabled={patch.isPending}
                    >
                      Reset
                    </Button>
                  </Box>
                </Stack>
              </CardContent>
            </Card>
          ))}
          {!q.isLoading && (q.data?.count || 0) === 0 ? (
            <Alert severity="info">No cases yet. Run Hard-Case Miner.</Alert>
          ) : null}
        </Stack>
      </Stack>
    </ProtectedRoute>
  );
};

export default LabellingPage;
