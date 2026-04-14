import { useEffect, useRef, useState } from 'react';
import type { Query } from '@tanstack/react-query';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Card from '@mui/material/Card';
import CardContent from '@mui/material/CardContent';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
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
  patchSettings,
  restartProcessor,
  type FileTestStatusPayload,
} from '../../api/api';
import { queryKeys } from '../../api/queryKeys';
import { useProtectedArea } from '../../contexts/ProtectedAreaContext';

const POLL_MS = 2000;

function statusPollInterval(query: Query<FileTestStatusPayload, Error>): number | false {
  if (query.state.status === 'error') return false;
  const d = query.state.data;
  if (!d || d.video_source !== 'file') return false;
  return POLL_MS;
}

function filesPollInterval(query: Query<Awaited<ReturnType<typeof fetchFileTestFiles>>, Error>): number | false {
  return query.state.status === 'error' ? false : POLL_MS;
}

type FileReplayCardProps = {
  /** Якорь для ссылок вида /library#file-replay */
  anchorId?: string;
};

export function FileReplayCard({ anchorId = 'file-replay' }: FileReplayCardProps = {}) {
  const { t } = useTranslation();
  const { isAdmin } = useProtectedArea();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loopLocal, setLoopLocal] = useState(false);
  const inactiveSeeded = useRef(false);
  /** Не перезаписывать switch из poll сразу после клика (убирает «дёргание» desired vs processor). */
  const loopQuietUntilRef = useRef(0);
  const [modeBanner, setModeBanner] = useState<{ severity: 'success' | 'error'; text: string } | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const statusQuery = useQuery({
    queryKey: ['file-test-status'],
    queryFn: fetchFileTestStatus,
    refetchInterval: statusPollInterval,
    retry: false,
  });

  const fileMode = statusQuery.isSuccess && statusQuery.data?.video_source === 'file';

  const filesQuery = useQuery({
    queryKey: ['file-test-files'],
    queryFn: fetchFileTestFiles,
    enabled: fileMode,
    refetchInterval: fileMode ? filesPollInterval : false,
    retry: false,
  });

  const inactive = statusQuery.isSuccess && statusQuery.data && statusQuery.data.video_source !== 'file';

  useEffect(() => {
    if (!inactive) {
      inactiveSeeded.current = false;
      return;
    }
    const d = statusQuery.data;
    if (!d || inactiveSeeded.current) return;
    setLoopLocal(!!d.config_loop_default);
    inactiveSeeded.current = true;
  }, [inactive, statusQuery.data]);

  const invalidateAfterConfigChange = () => {
    void qc.invalidateQueries({ queryKey: ['file-test-status'] });
    void qc.invalidateQueries({ queryKey: ['file-test-files'] });
    void qc.invalidateQueries({ queryKey: queryKeys.settings.all });
  };

  const enableFileReplayMut = useMutation({
    mutationFn: async () => {
      const dir = (statusQuery.data?.file_dir || '').trim() || '/app/data/file_test';
      await patchSettings({
        video: {
          source: 'file',
          file_dir: dir,
          file_loop: loopLocal,
        },
      });
      return restartProcessor();
    },
    onSuccess: (r) => {
      invalidateAfterConfigChange();
      inactiveSeeded.current = false;
      setModeBanner(
        r.success
          ? { severity: 'success', text: t('library.fileReplayRestartOk') }
          : { severity: 'error', text: r.message || t('library.fileReplayRestartFail') },
      );
    },
    onError: () => {
      setModeBanner({ severity: 'error', text: t('library.fileReplayConfigSaveFail') });
    },
  });

  const returnToLiveMut = useMutation({
    mutationFn: async () => {
      await patchSettings({ video: { source: 'go2rtc' } });
      return restartProcessor();
    },
    onSuccess: (r) => {
      invalidateAfterConfigChange();
      setModeBanner(
        r.success
          ? { severity: 'success', text: t('library.fileReplayRestartOk') }
          : { severity: 'error', text: r.message || t('library.fileReplayRestartFail') },
      );
    },
    onError: () => {
      setModeBanner({ severity: 'error', text: t('library.fileReplayConfigSaveFail') });
    },
  });

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
    onError: () => {
      loopQuietUntilRef.current = 0;
      void qc.invalidateQueries({ queryKey: ['file-test-status'] });
    },
  });

  useEffect(() => {
    if (loopMut.isPending) return;
    if (Date.now() < loopQuietUntilRef.current) return;
    const data = statusQuery.data;
    if (!data || data.video_source !== 'file') return;
    const d = data.desired as Record<string, unknown> | undefined;
    if (d && typeof d.loop === 'boolean') {
      setLoopLocal(d.loop);
      return;
    }
    const proc = data.processor as Record<string, unknown> | null | undefined;
    if (proc && typeof proc.loop === 'boolean') {
      setLoopLocal(proc.loop);
      return;
    }
    setLoopLocal(!!data.config_loop_default);
  }, [statusQuery.data, fileMode, loopMut.isPending]);

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
    onMutate: () => setUploadError(null),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['file-test-files'] });
      if (fileInputRef.current) fileInputRef.current.value = '';
    },
    onError: (err: unknown) => {
      const ax = err as {
        response?: {
          status?: number;
          data?: { error?: string } | string;
          headers?: { 'content-type'?: string };
        };
      };
      const st = ax.response?.status;
      const rawData = ax.response?.data;
      const apiErr =
        rawData && typeof rawData === 'object' && rawData !== null && 'error' in rawData
          ? String((rawData as { error?: string }).error || '')
          : '';
      const ct = ax.response?.headers?.['content-type'] ?? '';
      const likelyProxy413 =
        st === 413 && (!apiErr || String(ct).toLowerCase().includes('html'));
      const maxMb = statusQuery.data?.file_test_max_upload_mb;
      if (st === 413) {
        setUploadError(
          likelyProxy413
            ? t('library.fileReplayUpload413Proxy', { max: maxMb ?? '—' })
            : maxMb != null
              ? t('library.fileReplayUpload413', { max: maxMb })
              : t('library.fileReplayUpload413Generic'),
        );
      } else {
        setUploadError(apiErr || t('library.fileReplayUploadFailed'));
      }
    },
  });

  const resolvedDir = statusQuery.data?.file_dir ?? '';
  const desiredForLoop = statusQuery.data?.desired as Record<string, unknown> | undefined;
  const replayArmed = Boolean(desiredForLoop?.armed);

  const handleLoopChange = (_: unknown, v: boolean) => {
    setLoopLocal(v);
    loopQuietUntilRef.current = Date.now() + 4500;
    if (fileMode && replayArmed) loopMut.mutate(v);
  };

  if (statusQuery.isLoading) {
    return (
      <Card id={anchorId} sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
            {t('library.sectionFileReplay')}
          </Typography>
          <Typography variant="h6" gutterBottom>
            {t('library.fileReplayTitle')}
          </Typography>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (statusQuery.isError) {
    return (
      <Card id={anchorId} sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
            {t('library.sectionFileReplay')}
          </Typography>
          <Typography variant="h6" gutterBottom>
            {t('library.fileReplayTitle')}
          </Typography>
          <Alert severity="error">{t('library.fileReplayLoadError')}</Alert>
        </CardContent>
      </Card>
    );
  }

  if (inactive) {
    return (
      <Card id={anchorId} sx={{ mb: 2 }}>
        <CardContent>
          <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
            {t('library.sectionFileReplay')}
          </Typography>
          <Typography variant="h6" gutterBottom>
            {t('library.fileReplayTitle')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('library.fileReplaySetupIntro')}
          </Typography>
          {modeBanner ? (
            <Alert
              severity={modeBanner.severity}
              sx={{ mb: 2 }}
              onClose={() => setModeBanner(null)}
            >
              {modeBanner.text}
            </Alert>
          ) : null}
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('library.fileReplaySetupFolderInfo', {
              path: (statusQuery.data?.file_dir || '').trim() || '/app/data/file_test',
            })}
          </Typography>
          <Box sx={{ width: '100%', mb: 1 }}>
            <FormControlLabel
              control={
                <Switch
                  checked={loopLocal}
                  onChange={handleLoopChange}
                  disabled={!isAdmin || enableFileReplayMut.isPending}
                />
              }
              label={t('library.fileReplayLoop')}
            />
            <FormHelperText sx={{ ml: 0 }}>{t('library.fileReplayLoopHint')}</FormHelperText>
          </Box>
          <Button
            variant="contained"
            disabled={!isAdmin || enableFileReplayMut.isPending}
            onClick={() => {
              setModeBanner(null);
              enableFileReplayMut.mutate();
            }}
          >
            {t('library.fileReplayEnableButton')}
          </Button>
          {!isAdmin ? (
            <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
              {t('library.fileReplayAdminOnlyMode')}
            </Typography>
          ) : null}
        </CardContent>
      </Card>
    );
  }

  const proc = statusQuery.data?.processor as Record<string, unknown> | null | undefined;
  const desired = statusQuery.data?.desired as Record<string, unknown> | undefined;
  const armed = Boolean(desired?.armed);

  return (
    <Card id={anchorId} sx={{ mb: 2 }}>
      <CardContent>
        <Typography variant="subtitle2" color="text.secondary" sx={{ mb: 0.5 }}>
          {t('library.sectionFileReplay')}
        </Typography>
        <Typography variant="h6" gutterBottom>
          {t('library.fileReplayTitle')}
        </Typography>
        {modeBanner ? (
          <Alert
            severity={modeBanner.severity}
            sx={{ mb: 2 }}
            onClose={() => setModeBanner(null)}
          >
            {modeBanner.text}
          </Alert>
        ) : null}
        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }} alignItems="center">
          <Button
            variant="outlined"
            color="secondary"
            disabled={!isAdmin || returnToLiveMut.isPending}
            onClick={() => {
              setModeBanner(null);
              if (window.confirm(t('library.fileReplayReturnLiveConfirm'))) returnToLiveMut.mutate();
            }}
          >
            {t('library.fileReplayReturnLive')}
          </Button>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          {t('library.fileReplayHint')}
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('library.fileReplayFolderReadOnly', { path: resolvedDir || '—' })}
        </Typography>

        <Box sx={{ width: '100%', mb: 1 }}>
          <FormControlLabel
            control={
              <Switch
                checked={loopLocal}
                onChange={handleLoopChange}
                disabled={!isAdmin || loopMut.isPending}
              />
            }
            label={t('library.fileReplayLoop')}
          />
          <FormHelperText sx={{ ml: 0 }}>{t('library.fileReplayLoopHint')}</FormHelperText>
        </Box>

        <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mb: 2 }} alignItems="center">
          <Button
            variant="contained"
            color="primary"
            disabled={!isAdmin || runMut.isPending}
            onClick={() => runMut.mutate()}
          >
            {t('library.fileReplayStart')}
          </Button>
          <Button
            variant="outlined"
            color="warning"
            disabled={!isAdmin || stopMut.isPending}
            onClick={() => stopMut.mutate()}
          >
            {t('library.fileReplayStop')}
          </Button>
          <Chip
            size="small"
            label={`${t('library.fileReplayArmed')}: ${armed ? t('library.fileReplayYes') : t('library.fileReplayNo')}`}
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
        <Button
          size="small"
          variant="outlined"
          disabled={!isAdmin || upMut.isPending}
          onClick={() => fileInputRef.current?.click()}
        >
          {t('library.fileReplayUpload')}
        </Button>
        <FormHelperText sx={{ display: 'block', maxWidth: 560 }}>
          {statusQuery.data?.file_test_max_upload_mb != null
            ? t('library.fileReplayUploadLimitHint', { max: statusQuery.data.file_test_max_upload_mb })
            : t('library.fileReplayUploadLimitHintGeneric')}
        </FormHelperText>
        {uploadError ? (
          <Alert severity="error" sx={{ mt: 1, mb: 1 }} onClose={() => setUploadError(null)}>
            {uploadError}
          </Alert>
        ) : null}

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          {t('library.fileReplayProgress')}
        </Typography>
        {proc ? (
          <Stack spacing={0.5} sx={{ mb: 2 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 0.5 }}>
              {t('library.fileReplayLiveSummary', {
                phase: String(proc.phase ?? '—'),
                file: String(proc.current_file ?? '—'),
                index: String(proc.index ?? '—'),
                total: String(proc.total ?? '—'),
                frames: String(proc.frame_in_clip ?? '—'),
              })}
            </Typography>
            <Typography variant="body2">
              {t('library.fileReplayPhase')}: {String(proc.phase ?? '—')}
            </Typography>
            <Typography variant="body2">
              {t('library.fileReplayCurrent')}: {String(proc.current_file ?? '—')}
            </Typography>
            <Typography variant="body2">
              {t('library.fileReplayIndex')}: {String(proc.index ?? '—')} / {String(proc.total ?? '—')}
            </Typography>
            <Typography variant="body2">
              {t('library.fileReplayFrames')}: {String(proc.frame_in_clip ?? '—')}
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              {t('library.fileReplayFramesHint')}
            </Typography>
            {proc.last_error ? (
              <Typography variant="body2" color="error">
                {t('library.fileReplayError')}: {String(proc.last_error)}
              </Typography>
            ) : null}
          </Stack>
        ) : (
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            —
          </Typography>
        )}

        <Typography variant="subtitle2" sx={{ mb: 1 }}>
          {t('library.fileReplayFiles')}
        </Typography>
        {filesQuery.isLoading ? (
          <LinearProgress />
        ) : (
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>{t('library.fileReplayName')}</TableCell>
                <TableCell align="right">{t('library.fileReplaySize')}</TableCell>
                <TableCell align="right">{t('library.fileReplayDuration')}</TableCell>
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
                        if (window.confirm(`${t('library.fileReplayDelete')}? ${row.name}`))
                          delMut.mutate(row.name);
                      }}
                    >
                      {t('library.fileReplayDelete')}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {(runMut.isError || stopMut.isError || loopMut.isError || filesQuery.isError) && (
          <Box sx={{ mt: 2 }}>
            <Alert severity="error">{t('library.fileReplayActionError')}</Alert>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
