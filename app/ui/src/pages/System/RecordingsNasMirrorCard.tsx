import { useTranslation } from 'react-i18next';
import { useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControlLabel from '@mui/material/FormControlLabel';
import Paper from '@mui/material/Paper';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import axios from 'axios';
import { patchSettings } from '../../api/settingsSession';
import { queryKeys } from '../../api/queryKeys';
import { useSettingsQuery } from '../../hooks/useSettingsQueries';
import { restartProcessor } from '../../api/notificationsProcessor';
import { BASE_API_URL } from '../../api/client';

const MASK_PLACEHOLDER = '***';

function secretFieldForForm(raw: unknown): string {
  const s = String(raw ?? '').trim();
  if (!s || s === MASK_PLACEHOLDER) return '';
  return s;
}

type MirrorForm = {
  enabled: boolean;
  host: string;
  port: string;
  username: string;
  sftp_password: string;
  sftp_key_passphrase: string;
  remote_base_path: string;
  ssh_private_key_path: string;
  max_concurrent_uploads: string;
  upload_retries: string;
  retry_backoff_seconds: string;
  strict_host_key: boolean;
  known_hosts_path: string;
  delete_local_after_success: boolean;
};

function readMirrorFromSettings(data: unknown): MirrorForm {
  const root = data as { storage?: { recordings_mirror?: Record<string, unknown> } };
  const m = root?.storage?.recordings_mirror ?? {};
  return {
    enabled: Boolean(m.enabled),
    host: String(m.host ?? ''),
    port: String(m.port ?? '22'),
    username: String(m.username ?? ''),
    sftp_password: secretFieldForForm(m.sftp_password),
    sftp_key_passphrase: secretFieldForForm(m.sftp_key_passphrase),
    remote_base_path: String(m.remote_base_path ?? '/birdlense/recordings'),
    ssh_private_key_path: String(m.ssh_private_key_path ?? ''),
    max_concurrent_uploads: String(m.max_concurrent_uploads ?? '2'),
    upload_retries: String(m.upload_retries ?? '3'),
    retry_backoff_seconds: String(m.retry_backoff_seconds ?? '5'),
    strict_host_key: m.strict_host_key !== false,
    known_hosts_path: String(m.known_hosts_path ?? ''),
    delete_local_after_success: Boolean(m.delete_local_after_success),
  };
}

export const RecordingsNasMirrorCard = ({ enabled }: { enabled: boolean }) => {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useSettingsQuery(enabled);
  const [form, setForm] = useState<MirrorForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [errMsg, setErrMsg] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setForm(readMirrorFromSettings(data));
  }, [data]);

  const dirty = useMemo(() => {
    if (!data || !form) return false;
    const cur = readMirrorFromSettings(data);
    return JSON.stringify(cur) !== JSON.stringify(form);
  }, [data, form]);

  if (!enabled) {
    return null;
  }

  const onSave = async () => {
    if (!form) return;
    setSaving(true);
    setMessage(null);
    setErrMsg(null);
    try {
      let port = parseInt(form.port, 10);
      if (!Number.isFinite(port) || port < 1 || port > 65535) port = 22;
      let maxConc = parseInt(form.max_concurrent_uploads, 10);
      if (!Number.isFinite(maxConc)) maxConc = 2;
      maxConc = Math.min(8, Math.max(1, maxConc));
      let retries = parseInt(form.upload_retries, 10);
      if (!Number.isFinite(retries)) retries = 3;
      retries = Math.min(10, Math.max(1, retries));
      let backoff = parseFloat(form.retry_backoff_seconds);
      if (!Number.isFinite(backoff)) backoff = 5;
      backoff = Math.min(120, Math.max(1, backoff));

      const recordings_mirror: Record<string, unknown> = {
        enabled: form.enabled,
        protocol: 'sftp',
        host: form.host.trim(),
        port,
        username: form.username.trim(),
        remote_base_path: form.remote_base_path.trim() || '/birdlense/recordings',
        ssh_private_key_path: form.ssh_private_key_path.trim(),
        max_concurrent_uploads: maxConc,
        upload_retries: retries,
        retry_backoff_seconds: backoff,
        strict_host_key: form.strict_host_key,
        known_hosts_path: form.known_hosts_path.trim(),
        delete_local_after_success: form.delete_local_after_success,
      };
      const pw = form.sftp_password.trim();
      if (pw) {
        recordings_mirror.sftp_password = pw;
      }
      const kph = form.sftp_key_passphrase.trim();
      if (kph) {
        recordings_mirror.sftp_key_passphrase = kph;
      }

      await patchSettings({
        storage: {
          recordings_mirror,
        },
      });
      await queryClient.invalidateQueries({ queryKey: queryKeys.settings.all });
      const restart = await restartProcessor();
      setMessage(
        restart.success
          ? `${t('storage.nasMirrorSaved')} ${t('storage.nasMirrorProcessorRestartRequested')}`
          : t('storage.nasMirrorSaved'),
      );
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setErrMsg(msg);
    } finally {
      setSaving(false);
    }
  };

  const onTestConnection = async () => {
    setTesting(true);
    setMessage(null);
    setErrMsg(null);
    try {
      const { data: result } = await axios.post<{ ok?: boolean; error?: string }>(
        `${BASE_API_URL}/storage/recordings-mirror/test`,
        {},
        { withCredentials: true },
      );
      if (!result.ok) {
        throw new Error(result.error || t('storage.nasMirrorTestFailed'));
      }
      setMessage(t('storage.nasMirrorTestOk'));
    } catch (e) {
      const err = e as { response?: { data?: { error?: string } }; message?: string };
      setErrMsg(
        err.response?.data?.error ||
          err.message ||
          t('storage.nasMirrorTestFailed'),
      );
    } finally {
      setTesting(false);
    }
  };

  if (isLoading || !form) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Typography variant="body2">{t('common.loading')}</Typography>
      </Paper>
    );
  }

  if (isError) {
    return (
      <Paper variant="outlined" sx={{ p: 2 }}>
        <Alert severity="error">
          {error instanceof Error ? error.message : t('storage.nasMirrorLoadError')}
        </Alert>
      </Paper>
    );
  }

  return (
    <Paper variant="outlined" sx={{ p: 2 }}>
      <Typography variant="h6" gutterBottom>
        {t('storage.nasMirrorTitle')}
      </Typography>
      <Typography variant="body2" color="text.secondary" paragraph>
        {t('storage.nasMirrorIntro')}
      </Typography>
      <Stack spacing={2}>
        <FormControlLabel
          control={
            <Switch
              checked={form.enabled}
              onChange={(_, v) => setForm((f) => (f ? { ...f, enabled: v } : f))}
            />
          }
          label={t('storage.nasMirrorEnabled')}
        />
        <TextField
          label={t('storage.nasMirrorHost')}
          value={form.host}
          onChange={(e) => setForm((f) => (f ? { ...f, host: e.target.value } : f))}
          fullWidth
          autoComplete="off"
        />
        <TextField
          label={t('storage.nasMirrorPort')}
          value={form.port}
          onChange={(e) => setForm((f) => (f ? { ...f, port: e.target.value } : f))}
          sx={{ maxWidth: 160 }}
        />
        <TextField
          label={t('storage.nasMirrorUsername')}
          value={form.username}
          onChange={(e) => setForm((f) => (f ? { ...f, username: e.target.value } : f))}
          fullWidth
          autoComplete="username"
        />
        <TextField
          label={t('storage.nasMirrorSftpPassword')}
          type="password"
          value={form.sftp_password}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, sftp_password: e.target.value } : f))
          }
          fullWidth
          autoComplete="new-password"
          helperText={t('storage.nasMirrorSftpPasswordHint')}
        />
        <TextField
          label={t('storage.nasMirrorKeyPassphrase')}
          type="password"
          value={form.sftp_key_passphrase}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, sftp_key_passphrase: e.target.value } : f))
          }
          fullWidth
          autoComplete="new-password"
          helperText={t('storage.nasMirrorKeyPassphraseHint')}
        />
        <TextField
          label={t('storage.nasMirrorRemoteBase')}
          value={form.remote_base_path}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, remote_base_path: e.target.value } : f))
          }
          fullWidth
          helperText={t('storage.nasMirrorRemoteBaseHint')}
        />
        <TextField
          label={t('storage.nasMirrorKeyPath')}
          value={form.ssh_private_key_path}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, ssh_private_key_path: e.target.value } : f))
          }
          fullWidth
          helperText={t('storage.nasMirrorKeyPathHint')}
        />
        <TextField
          label={t('storage.nasMirrorMaxConcurrent')}
          value={form.max_concurrent_uploads}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, max_concurrent_uploads: e.target.value } : f))
          }
          sx={{ maxWidth: 200 }}
        />
        <TextField
          label={t('storage.nasMirrorRetries')}
          value={form.upload_retries}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, upload_retries: e.target.value } : f))
          }
          sx={{ maxWidth: 200 }}
        />
        <TextField
          label={t('storage.nasMirrorBackoff')}
          value={form.retry_backoff_seconds}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, retry_backoff_seconds: e.target.value } : f))
          }
          sx={{ maxWidth: 200 }}
        />
        <FormControlLabel
          control={
            <Switch
              checked={form.strict_host_key}
              onChange={(_, v) => setForm((f) => (f ? { ...f, strict_host_key: v } : f))}
            />
          }
          label={t('storage.nasMirrorStrictHostKey')}
        />
        <TextField
          label={t('storage.nasMirrorKnownHosts')}
          value={form.known_hosts_path}
          onChange={(e) =>
            setForm((f) => (f ? { ...f, known_hosts_path: e.target.value } : f))
          }
          fullWidth
          helperText={t('storage.nasMirrorKnownHostsHint')}
        />
        <FormControlLabel
          control={
            <Switch
              checked={form.delete_local_after_success}
              onChange={(_, v) =>
                setForm((f) => (f ? { ...f, delete_local_after_success: v } : f))
              }
            />
          }
          label={t('storage.nasMirrorDeleteLocal')}
        />
        <Alert severity="warning">{t('storage.nasMirrorDeleteLocalWarn')}</Alert>
        <Alert severity="info" variant="outlined">
          {t('storage.nasMirrorEnvOverrideHint')}
        </Alert>
        {message ? (
          <Alert severity="success" onClose={() => setMessage(null)}>
            {message}
          </Alert>
        ) : null}
        {errMsg ? (
          <Alert severity="error" onClose={() => setErrMsg(null)}>
            {errMsg}
          </Alert>
        ) : null}
        <Box>
          <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1.5}>
            <Button
              variant="contained"
              onClick={() => void onSave()}
              disabled={saving || !dirty}
            >
              {saving ? t('common.loading') : t('storage.nasMirrorSave')}
            </Button>
            <Button
              variant="outlined"
              onClick={() => void onTestConnection()}
              disabled={testing || dirty}
            >
              {testing ? t('common.loading') : t('storage.nasMirrorTest')}
            </Button>
          </Stack>
        </Box>
      </Stack>
    </Paper>
  );
};
