import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import Typography from '@mui/material/Typography';
import {
  fetchFileTestFiles,
  fetchFileTestStatus,
  fileTestDeleteFile,
  fileTestRun,
  fileTestStop,
  fileTestUpload,
} from '../../api/api';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';

const POLL_MS = 2000;

export function FileTestRunCard() {
  const { t } = useTranslation();
  const { isAdmin } = useProtectedArea();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loopLocal, setLoopLocal] = useState(false);

  const statusQuery = useQuery({
    queryKey: ['file-test-status'],
    queryFn: fetchFileTestStatus,
    refetchInterval: POLL_MS,
    retry: false,
  });

  const filesQuery = useQuery({
    queryKey: ['file-test-files'],
    queryFn: fetchFileTestFiles,
    enabled: statusQuery.isSuccess && statusQuery.data?.video_source === 'file',
    refetchInterval: POLL_MS,
    retry: false,
  });

  const inactive = statusQuery.isError || (statusQuery.data && statusQuery.data.video_source !== 'file');

  useEffect(() => {
    const data = statusQuery.data;
    if (!data) return;
    const d = data.desired as Record<string, unknown> | undefined;
    if (d && typeof d.loop === 'boolean') {
      setLoopLocal(d.loop);
    } else {
      setLoopLocal(!!data.config_loop_default);
    }
  }, [statusQuery.data]);

  const runMut = useMutation({
    mutationFn: () => fileTestRun({ armed: true, loop: loopLocal }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['file-test-status'] });
    },
  });

  const loopMut = useMutation({
    mutationFn: (v: boolean) => fileTestRun({ loop: v }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['file-test-status'] });
    },
  });

  const stopMut = useMutation({
    mutationFn: () => fileTestStop(),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['file-test-status'] });
    },
  });

  const delMut = useMutation({
    mutationFn: (name: string) => fileTestDeleteFile(name),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['file-test-files'] });
    },
  });

  const upMut = useMutation({
    mutationFn: (f: File) => fileTestUpload(f),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['file-test-files'] });
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
  });

  if (statusQuery.isLoading) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (inactive) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {t('system.fileTestTitle')}
          </Typography>
          <Alert severity="info">{t('system.fileTestInactive')}</Alert>
        </CardContent>
      </Card>
    );
  }

  const proc = statusQuery.data?.processor as Record<string, unknown> | null | undefined;
  const desired = statusQuery.data?.desired as Record<string, unknown> | undefined;
  const armed = Boolean(desired?.armed);

  return (
    <Card sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="h6" gutterBottom>
          {t('system.fileTestTitle')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('system.fileTestHint')}
        </Typography>

        <Typography variant="caption" color="text.secondary" display="block" sx={{ mb: 1 }}>
          {t('system.fileTestDir')}: {statusQuery.data?.file_dir}
        </Typography>

        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }} alignItems="center">
          <FormControlLabel
            control={
              <Switch
                checked={loopLocal}
                onChange={(_, v) => {
                  setLoopLocal(v);
                  if (armed) loopMut.mutate(v);
                }}
                disabled={!isAdmin || loopMut.isPending}
              />
            }
            label={t('system.fileTestLoop')}
          />
          <Button
            variant="contained"
            color="primary"
            disabled={!isAdmin || runMut.isPending}
            onClick={() => runMut.mutate()}
          >
            {t('system.fileTestStart')}
          </Button>
          <Button
            variant="outlined"
            color="warning"
            disabled={!isAdmin || stopMut.isPending}
            onClick={() => stopMut.mutate()}
          >
            {t('system.fileTestStop')}
          </Button>
          <Chip
            size="small"
            label={`${t('system.fileTestArmed')}: ${armed ? t('system.fileTestYes') : t('system.fileTestNo')}`}
            color={armed ? 'success' : 'default'}
            variant="outlined"
          />
        </Stack>

        <input
          ref={fileInputRef}
          type="file"
          accept=".mp4,.mov,.mkv,video/mp4"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) upMut.mutate(f);
          }}
        />
        <Button size="small" variant="outlined" disabled={!isAdmin || upMut.isPending} onClick={() => fileInputRef.current?.click()}>
          {t('system.fileTestUpload')}
        </Button>

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          {t('system.fileTestProgress')}
        </Typography>
        {proc ? (
          <Stack spacing={0.5} sx={{ mb: 2 }}>
            <Typography variant="body2">
              {t('system.fileTestPhase')}: {String(proc.phase ?? '—')}
            </Typography>
            <Typography variant="body2">
              {t('system.fileTestCurrent')}: {String(proc.current_file ?? '—')}
            </Typography>
            <Typography variant="body2">
              {t('system.fileTestIndex')}: {String(proc.index ?? '—')} / {String(proc.total ?? '—')}
            </Typography>
            <Typography variant="body2">
              {t('system.fileTestFrames')}: {String(proc.frame_in_clip ?? '—')}
            </Typography>
            {proc.last_error ? (
              <Typography variant="body2" color="error">
                {t('system.fileTestError')}: {String(proc.last_error)}
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            —
          </Typography>
        )}

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {t('system.fileTestFiles')}
        </Typography>
        {filesQuery.isLoading ? (
          <LinearProgress />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('system.fileTestName')}</TableCell>
                <TableCell align="right">{t('system.fileTestSize')}</TableCell>
                <TableCell align="right">{t('system.fileTestDuration')}</TableCell>
                <TableCell align="right" />
              </TableRow>
            </TableHead>
            <TableBody>
              {(filesQuery.data?.files ?? []).map((row) => (
                <TableRow key={row.name}>
                  <TableCell>{row.name}</TableCell>
                  <TableCell align="right">{row.size}</TableCell>
                  <TableCell align="right">
                    {row.duration_sec != null ? Math.round(row.duration_sec * 10) / 10 : '—'}
                  </TableCell>
                  <TableCell align="right">
                    <Button
                      size="small"
                      color="error"
                      disabled={!isAdmin || delMut.isPending}
                      onClick={() => {
                        if (window.confirm(`${t('system.fileTestDelete')}? ${row.name}`))
                          delMut.mutate(row.name);
                      }}
                    >
                      {t('system.fileTestDelete')}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {(runMut.isError ||
          stopMut.isError ||
          upMut.isError ||
          loopMut.isError ||
          filesQuery.isError) && (
          <Box sx={{ mt: 2 }}>
            <Alert severity="error">{t('system.fileTestLoadError')}</Alert>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
