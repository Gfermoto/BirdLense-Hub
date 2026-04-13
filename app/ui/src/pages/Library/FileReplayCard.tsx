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
import TextField from '@mui/material/TextField';
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

export function FileReplayCard() {
  const { t } = useTranslation();
  const { isAdmin } = useProtectedArea();
  const qc = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loopLocal, setLoopLocal] = useState(false);
  const [setupDir, setSetupDir] = useState('');
  const [setupLoop, setSetupLoop] = useState(false);
  const [activeFolderDraft, setActiveFolderDraft] = useState('');
  const inactiveSeeded = useRef(false);
  const activeFolderSeeded = useRef(false);
  const [modeBanner, setModeBanner] = useState<{ severity: 'success' | 'error'; text: string } | null>(null);

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
    setSetupDir(d.file_dir || '');
    setSetupLoop(!!d.config_loop_default);
    inactiveSeeded.current = true;
  }, [inactive, statusQuery.data]);

  useEffect(() => {
    if (!fileMode) {
      activeFolderSeeded.current = false;
      return;
    }
    const dir = statusQuery.data?.file_dir;
    if (dir && !activeFolderSeeded.current) {
      setActiveFolderDraft(dir);
      activeFolderSeeded.current = true;
    }
  }, [fileMode, statusQuery.data?.file_dir]);

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

  const invalidateAfterConfigChange = () => {
    void qc.invalidateQueries({ queryKey: ['file-test-status'] });
    void qc.invalidateQueries({ queryKey: ['file-test-files'] });
    void qc.invalidateQueries({ queryKey: queryKeys.settings.all });
  };

  const enableFileReplayMut = useMutation({
    mutationFn: async () => {
      const dir = setupDir.trim() || '/app/data/file_test';
      await patchSettings({
        video: {
          source: 'file',
          file_dir: dir,
          file_loop: setupLoop,
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
      activeFolderSeeded.current = false;
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

  const saveFolderMut = useMutation({
    mutationFn: async () => {
      await patchSettings({
        video: { file_dir: activeFolderDraft.trim() },
      });
      return restartProcessor();
    },
    onSuccess: (r) => {
      activeFolderSeeded.current = false;
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

  const resolvedDir = statusQuery.data?.file_dir ?? '';
  const folderDirty =
    fileMode && activeFolderDraft.trim() !== '' && activeFolderDraft.trim() !== resolvedDir;

  if (statusQuery.isLoading) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
          <LinearProgress />
        </CardContent>
      </Card>
    );
  }

  if (statusQuery.isError) {
    return (
      <Card sx={{ mb: 2 }}>
        <CardContent>
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
      <Card sx={{ mb: 2 }}>
        <CardContent>
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
          <TextField
            fullWidth
            label={t('library.fileReplayDir')}
            value={setupDir}
            onChange={(e) => setSetupDir(e.target.value)}
            placeholder="/app/data/file_test"
            helperText={t('library.fileReplayFolderHint')}
            sx={{ mb: 2 }}
            disabled={!isAdmin || enableFileReplayMut.isPending}
          />
          <FormControlLabel
            control={
              <Switch
                checked={setupLoop}
                onChange={(_, v) => setSetupLoop(v)}
                disabled={!isAdmin || enableFileReplayMut.isPending}
              />
            }
            label={t('library.fileReplayLoopDefault')}
            sx={{ mb: 1, display: 'block' }}
          />
          <FormHelperText sx={{ mb: 2 }}>{t('library.fileReplayLoopDefaultHint')}</FormHelperText>
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
    <Card sx={{ mb: 2 }}>
      <CardContent>
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
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t('library.fileReplayHint')}
        </Typography>

        <TextField
          fullWidth
          size="small"
          label={t('library.fileReplayDir')}
          value={activeFolderDraft}
          onChange={(e) => setActiveFolderDraft(e.target.value)}
          helperText={t('library.fileReplayFolderHintActive')}
          sx={{ mb: 1 }}
          disabled={!isAdmin || saveFolderMut.isPending}
        />
        <Button
          size="small"
          variant="outlined"
          disabled={!isAdmin || saveFolderMut.isPending || !folderDirty}
          onClick={() => {
            setModeBanner(null);
            saveFolderMut.mutate();
          }}
          sx={{ mb: 2 }}
        >
          {t('library.fileReplayApplyFolder')}
        </Button>

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
            label={t('library.fileReplayLoop')}
          />
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

        <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
          {t('library.fileReplayProgress')}
        </Typography>
        {proc ? (
          <Stack spacing={0.5} sx={{ mb: 2 }}>
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

        {(runMut.isError ||
          stopMut.isError ||
          upMut.isError ||
          loopMut.isError ||
          filesQuery.isError) && (
          <Box sx={{ mt: 2 }}>
            <Alert severity="error">{t('library.fileReplayActionError')}</Alert>
          </Box>
        )}
      </CardContent>
    </Card>
  );
}
