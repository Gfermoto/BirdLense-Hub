import { useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Checkbox from '@mui/material/Checkbox';
import Chip from '@mui/material/Chip';
import FormControlLabel from '@mui/material/FormControlLabel';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import { getApiErrorMessage } from '../../api/api';
import {
  fetchProcessorWeightsStatus,
  resetProcessorWeights,
  restartProcessor,
  uploadProcessorWeight,
  type ProcessorWeightsSlotStatus,
} from '../../api/notificationsProcessor';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

function formatBytes(n: number | null | undefined): string {
  if (n == null || n < 0) return '—';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KiB`;
  if (n < 1024 * 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MiB`;
  return `${(n / (1024 * 1024 * 1024)).toFixed(2)} GiB`;
}

function SlotRow(props: {
  title: string;
  hint: string;
  slot: ProcessorWeightsSlotStatus;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  onPick: () => void;
  busy: boolean;
  onReset: () => void;
  resetLabel: string;
}) {
  const { t } = useTranslation();
  const { title, hint, slot, fileInputRef, onPick, busy, onReset, resetLabel } =
    props;
  return (
    <Box sx={{ py: 1.5, borderBottom: 1, borderColor: 'divider' }}>
      <Typography variant="subtitle1" fontWeight={600}>
        {title}
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {hint}
      </Typography>
      <Stack
        direction="row"
        flexWrap="wrap"
        alignItems="center"
        gap={1}
        sx={{ mb: 1 }}
      >
        <Chip
          size="small"
          color={slot.uses_custom_dir ? 'primary' : 'default'}
          label={
            slot.uses_custom_dir
              ? t('system.processorWeightsSourceCustom')
              : t('system.processorWeightsSourceBuiltin')
          }
        />
        <Typography variant="caption" color="text.secondary">
          {formatBytes(slot.bytes)}
          {slot.mtime_unix
            ? ` · ${t('system.processorWeightsMtime', {
                ts: new Date(slot.mtime_unix * 1000).toLocaleString(),
              })}`
            : ''}
        </Typography>
      </Stack>
      {slot.fingerprint_sha256_16 ? (
        <Typography
          variant="caption"
          color="text.secondary"
          component="div"
          sx={{
            mb: 1,
            fontFamily: 'ui-monospace, monospace',
            wordBreak: 'break-all',
          }}
        >
          {t('system.processorWeightsFingerprint', {
            fp: slot.fingerprint_sha256_16,
          })}
        </Typography>
      ) : null}
      <Stack direction="row" flexWrap="wrap" gap={1}>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pt"
          hidden
          onChange={onPick}
        />
        <Button
          size="small"
          variant="outlined"
          disabled={busy}
          onClick={() => fileInputRef.current?.click()}
        >
          {t('system.processorWeightsUploadPt')}
        </Button>
        <Button size="small" color="warning" disabled={busy} onClick={onReset}>
          {resetLabel}
        </Button>
      </Stack>
    </Box>
  );
}

export type ProcessorWeightsCardPlacement =
  | 'settingsModels'
  | 'systemWorkspace';

type ProcessorWeightsCardProps = {
  /** Веса в блоке «Настройки → Процессор» (без оболочки System) или на странице Система (устар.). */
  placement?: ProcessorWeightsCardPlacement;
};

export function ProcessorWeightsCard({
  placement = 'settingsModels',
}: ProcessorWeightsCardProps) {
  const { t } = useTranslation();
  const inline = placement === 'settingsModels';
  const qc = useQueryClient();
  const [info, setInfo] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ackClassifier, setAckClassifier] = useState(false);
  const binaryRef = useRef<HTMLInputElement>(null);
  const classifierRef = useRef<HTMLInputElement>(null);
  const allowRef = useRef<HTMLInputElement>(null);

  const statusQ = useQuery({
    queryKey: queryKeys.systemPanels.processorWeightsStatus,
    queryFn: fetchProcessorWeightsStatus,
  });

  const uploadMut = useMutation({
    mutationFn: async (args: {
      role: 'binary' | 'classifier' | 'class_names';
      file: File;
      ack?: boolean;
    }) => {
      const r = await uploadProcessorWeight(args.role, args.file, {
        acknowledgeClassifierOnly: args.ack,
      });
      if (!r.ok) throw new Error(r.error || 'upload_failed');
      return r;
    },
    onSuccess: async () => {
      setErr(null);
      setInfo(t('system.processorWeightsUploadOk'));
      await qc.invalidateQueries({
        queryKey: queryKeys.systemPanels.processorWeightsStatus,
      });
    },
    onError: (e: unknown) => {
      const code = e instanceof Error ? e.message : '';
      const key = code ? `system.processorWeightsError.${code}` : '';
      const mapped = key ? t(key, { defaultValue: code }) : '';
      setErr(
        mapped ||
          getApiErrorMessage(e, t('system.processorWeightsUploadFailed')),
      );
      setInfo(null);
    },
  });

  const resetMut = useMutation({
    mutationFn: async (
      roles: Array<'binary' | 'classifier' | 'class_names' | 'all'>,
    ) => {
      const r = await resetProcessorWeights(roles);
      if (!r.ok) throw new Error(r.error || 'reset_failed');
      return r;
    },
    onSuccess: async () => {
      setErr(null);
      setInfo(t('system.processorWeightsResetOk'));
      await qc.invalidateQueries({
        queryKey: queryKeys.systemPanels.processorWeightsStatus,
      });
    },
    onError: (e: unknown) => {
      setErr(getApiErrorMessage(e, t('system.processorWeightsResetFailed')));
      setInfo(null);
    },
  });

  const restartMut = useMutation({
    mutationFn: async () => {
      const r = await restartProcessor();
      if (!r.success) throw new Error(r.message || 'restart_failed');
      return r;
    },
    onSuccess: (r) => {
      setErr(null);
      setInfo(r.message || t('system.processorWeightsRestartOk'));
    },
    onError: (e: unknown) => {
      setErr(getApiErrorMessage(e, t('system.processorWeightsRestartFailed')));
    },
  });

  const busy =
    uploadMut.isPending || resetMut.isPending || restartMut.isPending;

  const onBinaryFile = () => {
    const f = binaryRef.current?.files?.[0];
    if (f) uploadMut.mutate({ role: 'binary', file: f });
    if (binaryRef.current) binaryRef.current.value = '';
  };

  const onClassifierFile = () => {
    const f = classifierRef.current?.files?.[0];
    if (f) {
      uploadMut.mutate({
        role: 'classifier',
        file: f,
        ack: ackClassifier,
      });
    }
    if (classifierRef.current) classifierRef.current.value = '';
  };

  const onAllowFile = () => {
    const f = allowRef.current?.files?.[0];
    if (f) uploadMut.mutate({ role: 'class_names', file: f });
    if (allowRef.current) allowRef.current.value = '';
  };

  const introKey = inline
    ? 'settings.processorWeightsIntroInline'
    : 'system.processorWeightsIntro';

  const errorBody = (
    <>
      <Typography variant={inline ? 'subtitle1' : 'h6'} fontWeight={600}>
        {t('system.processorWeightsTitle')}
      </Typography>
      <Alert severity="error" variant="outlined" sx={{ mt: 1 }}>
        {getApiErrorMessage(
          statusQ.error,
          t('system.processorWeightsLoadError'),
        )}
      </Alert>
    </>
  );

  if (statusQ.isError) {
    return inline ? (
      <Box id="processor-weights" sx={{ mt: 2, minWidth: 0, maxWidth: '100%' }}>
        {errorBody}
      </Box>
    ) : (
      <SystemCardShell
        title={t('system.processorWeightsTitle')}
        description={t('system.processorWeightsIntro')}
        statusLabel={t('system.configAuditNeedsReview')}
        statusTone="error"
      >
        {errorBody}
      </SystemCardShell>
    );
  }

  const st = statusQ.data;

  const inner = (
    <Box>
      {info ? (
        <Alert
          severity="success"
          variant="outlined"
          sx={{ mb: 2 }}
          onClose={() => setInfo(null)}
        >
          {info}
        </Alert>
      ) : null}
      {err ? (
        <Alert
          severity="error"
          variant="outlined"
          sx={{ mb: 2 }}
          onClose={() => setErr(null)}
        >
          {err}
        </Alert>
      ) : null}

      {st ? (
        <>
          <SlotRow
            title={t('system.processorWeightsBinary')}
            hint={t('system.processorWeightsBinaryHint')}
            slot={st.binary}
            fileInputRef={binaryRef}
            onPick={onBinaryFile}
            busy={busy}
            onReset={() => resetMut.mutate(['binary'])}
            resetLabel={t('system.processorWeightsResetBinary')}
          />
          <SlotRow
            title={t('system.processorWeightsClassifier')}
            hint={t('system.processorWeightsClassifierHint')}
            slot={st.classifier}
            fileInputRef={classifierRef}
            onPick={onClassifierFile}
            busy={busy}
            onReset={() => resetMut.mutate(['classifier'])}
            resetLabel={t('system.processorWeightsResetClassifier')}
          />
          <FormControlLabel
            sx={{ mt: 1, display: 'block' }}
            control={
              <Checkbox
                checked={ackClassifier}
                onChange={(_, c) => setAckClassifier(c)}
                size="small"
              />
            }
            label={t('system.processorWeightsAckClassifier')}
          />
          <Box sx={{ py: 1.5, borderBottom: 1, borderColor: 'divider' }}>
            <Typography variant="subtitle1" fontWeight={600}>
              {t('system.processorWeightsAllowlist')}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
              {t('system.processorWeightsAllowlistHint')}
            </Typography>
            <Stack
              direction="row"
              flexWrap="wrap"
              alignItems="center"
              gap={1}
              sx={{ mb: 1 }}
            >
              <Chip
                size="small"
                color={st.allowlist.uses_custom_dir ? 'primary' : 'default'}
                label={
                  st.allowlist.uses_custom_dir
                    ? t('system.processorWeightsSourceCustom')
                    : t('system.processorWeightsSourceBuiltin')
                }
              />
              <Typography variant="caption" color="text.secondary">
                {formatBytes(st.allowlist.bytes)}
                {st.allowlist.mtime_unix
                  ? ` · ${t('system.processorWeightsMtime', {
                      ts: new Date(
                        st.allowlist.mtime_unix * 1000,
                      ).toLocaleString(),
                    })}`
                  : ''}
              </Typography>
            </Stack>
            {st.allowlist.fingerprint_sha256_16 ? (
              <Typography
                variant="caption"
                color="text.secondary"
                component="div"
                sx={{
                  mb: 1,
                  fontFamily: 'ui-monospace, monospace',
                  wordBreak: 'break-all',
                }}
              >
                {t('system.processorWeightsFingerprint', {
                  fp: st.allowlist.fingerprint_sha256_16,
                })}
              </Typography>
            ) : null}
            <Stack direction="row" flexWrap="wrap" gap={1}>
              <input
                ref={allowRef}
                type="file"
                accept=".txt,text/plain"
                hidden
                onChange={onAllowFile}
              />
              <Button
                size="small"
                variant="outlined"
                disabled={busy}
                onClick={() => allowRef.current?.click()}
              >
                {t('system.processorWeightsUploadTxt')}
              </Button>
              <Button
                size="small"
                color="warning"
                disabled={busy}
                onClick={() => resetMut.mutate(['class_names'])}
              >
                {t('system.processorWeightsResetAllowlist')}
              </Button>
            </Stack>
          </Box>
          <Typography
            variant="caption"
            color="text.secondary"
            display="block"
            sx={{ mt: 1 }}
          >
            {t('system.processorWeightsDirLabel')}: {st.custom_weights_dir}
          </Typography>
        </>
      ) : null}

      <Stack direction="row" flexWrap="wrap" gap={1} sx={{ mt: 2 }}>
        <Button
          variant="outlined"
          color="warning"
          disabled={busy || !st}
          onClick={() => resetMut.mutate(['all'])}
        >
          {t('system.processorWeightsResetAll')}
        </Button>
        <Button
          variant="contained"
          disabled={busy}
          onClick={() => restartMut.mutate()}
        >
          {t('system.processorWeightsRestartProcessor')}
        </Button>
      </Stack>
    </Box>
  );

  if (inline) {
    return (
      <Box id="processor-weights" sx={{ mt: 2, minWidth: 0, maxWidth: '100%' }}>
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mb: 1 }}
        >
          <Typography variant="subtitle1" fontWeight={600}>
            {t('system.processorWeightsTitle')}
          </Typography>
          <Chip
            size="small"
            color={busy ? 'warning' : 'default'}
            label={
              busy
                ? t('system.catalogRepairRunning')
                : t('system.readinessReady')
            }
          />
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          {t(introKey)}
        </Typography>
        {inner}
      </Box>
    );
  }

  return (
    <SystemCardShell
      id="processor-weights"
      title={t('system.processorWeightsTitle')}
      description={t(introKey)}
      statusLabel={
        busy ? t('system.catalogRepairRunning') : t('system.readinessReady')
      }
      statusTone={busy ? 'warning' : 'default'}
    >
      {inner}
    </SystemCardShell>
  );
}
