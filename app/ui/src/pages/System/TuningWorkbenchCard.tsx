import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Divider from '@mui/material/Divider';
import FormControl from '@mui/material/FormControl';
import InputLabel from '@mui/material/InputLabel';
import LinearProgress from '@mui/material/LinearProgress';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import {
  applyTuningPreset,
  fetchTuningWorkbench,
  rollbackTuningProfile,
  saveCameraTuningProfile,
} from '../../api/systemAuditMetrics';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';
import {
  CAMERA_TUNING_FIELD_DEFS,
  cameraTuningRoleLabelKey,
} from '../Settings/shared/cameraTuningFields';

type CameraOverrideDraft = Record<string, string>;

function fmtDelta(v: number): string {
  if (v > 0) return `+${v.toFixed(2)}`;
  return v.toFixed(2);
}

function draftFromOverrides(overrides: Record<string, unknown> | undefined): CameraOverrideDraft {
  const out: CameraOverrideDraft = {};
  if (!overrides) return out;
  for (const def of CAMERA_TUNING_FIELD_DEFS) {
    const v = overrides[def.key];
    if (v === undefined || v === null) continue;
    out[def.key] = String(v);
  }
  return out;
}

export function TuningWorkbenchCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [selectedCamera, setSelectedCamera] = useState('');
  const [draft, setDraft] = useState<CameraOverrideDraft>({});

  const q = useQuery({
    queryKey: queryKeys.systemPanels.tuningWorkbench,
    queryFn: fetchTuningWorkbench,
    staleTime: 20_000,
  });

  const refresh = () =>
    qc.invalidateQueries({ queryKey: queryKeys.systemPanels.tuningWorkbench });

  const applyPresetMutation = useMutation({
    mutationFn: applyTuningPreset,
    onSuccess: refresh,
  });
  const saveCameraMutation = useMutation({
    mutationFn: (payload: { cameraId: string; overrides: Record<string, unknown> }) =>
      saveCameraTuningProfile(payload.cameraId, payload.overrides),
    onSuccess: refresh,
  });
  const rollbackMutation = useMutation({
    mutationFn: rollbackTuningProfile,
    onSuccess: refresh,
  });

  const cameraProfiles = q.data?.camera_profiles;
  const activeCamera = useMemo(
    () => (cameraProfiles ?? []).find((row) => row.camera_id === selectedCamera),
    [cameraProfiles, selectedCamera],
  );

  useEffect(() => {
    setDraft(draftFromOverrides(activeCamera?.overrides));
  }, [activeCamera?.camera_id, activeCamera?.overrides]);

  const parseNumber = (raw: string): number | undefined => {
    const text = raw.trim();
    if (!text) return undefined;
    const parsed = Number(text);
    if (!Number.isFinite(parsed)) return undefined;
    return parsed;
  };

  const toOverrides = (): Record<string, unknown> => {
    const out: Record<string, unknown> = {};
    for (const def of CAMERA_TUNING_FIELD_DEFS) {
      const raw = draft[def.key];
      if (raw == null || raw === '') continue;
      if (def.kind === 'boolean') {
        out[def.key] = raw === 'true' || raw === '1';
        continue;
      }
      const n = parseNumber(raw);
      if (n != null) out[def.key] = n;
    }
    return out;
  };

  if (q.isLoading) return <LinearProgress />;
  if (q.error || !q.data) {
    return (
      <Alert severity="warning" variant="outlined">
        {t('system.tuningWorkbenchLoadError')}
      </Alert>
    );
  }

  const globalGuardrailErrors = q.data.global.guardrails.errors ?? [];
  const globalGuardrailWarnings = q.data.global.guardrails.warnings ?? [];
  const lastEval = q.data.last_change?.auto_eval;
  const mutating =
    applyPresetMutation.isPending ||
    saveCameraMutation.isPending ||
    rollbackMutation.isPending;

  return (
    <SystemCardShell
      title={t('system.tuningWorkbenchTitle')}
      description={t('system.tuningWorkbenchHint')}
      statusLabel={globalGuardrailErrors.length ? t('system.configAuditNeedsReview') : t('system.readinessReady')}
      statusTone={globalGuardrailErrors.length ? 'warning' : 'success'}
    >
      <Stack spacing={1.25}>
        <Typography variant="body2">
          {t('system.tuningWorkbenchGlobal')}: R {q.data.global.estimated.estimated_recall.toFixed(1)} · P{' '}
          {q.data.global.estimated.estimated_precision.toFixed(1)} · Cost{' '}
          {q.data.global.estimated.estimated_runtime_cost.toFixed(1)}
        </Typography>

        {globalGuardrailErrors.length > 0 ? (
          <Alert severity="error" variant="outlined">
            {globalGuardrailErrors.join(' ')}
          </Alert>
        ) : null}
        {globalGuardrailWarnings.length > 0 ? (
          <Alert severity="warning" variant="outlined">
            {globalGuardrailWarnings.join(' ')}
          </Alert>
        ) : null}

        <Divider />
        <Typography variant="subtitle2">{t('system.tuningWorkbenchPresets')}</Typography>
        <Stack direction="row" useFlexGap flexWrap="wrap" gap={1}>
          {q.data.presets.map((preset) => (
            <Button
              key={preset.id}
              variant="outlined"
              size="small"
              disabled={mutating}
              onClick={() => applyPresetMutation.mutate(preset.id)}
            >
              {preset.title} ({fmtDelta(preset.delta_vs_current.recall_delta)} R /{' '}
              {fmtDelta(preset.delta_vs_current.precision_delta)} P)
            </Button>
          ))}
        </Stack>

        <Divider />
        <Typography variant="subtitle2">{t('system.tuningWorkbenchPerCamera')}</Typography>
        <FormControl size="small" sx={{ maxWidth: 320 }}>
          <InputLabel>{t('system.cameraLabel')}</InputLabel>
          <Select
            label={t('system.cameraLabel')}
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(String(e.target.value || ''))}
          >
            {q.data.available_cameras.map((cameraId) => (
              <MenuItem key={cameraId} value={cameraId}>
                {cameraId}
              </MenuItem>
            ))}
          </Select>
        </FormControl>
        {selectedCamera ? (
          <Stack spacing={1}>
            {activeCamera?.tuning_role ? (
              <Typography variant="caption" color="text.secondary">
                {t('settings.cameraTuningRole')}:{' '}
                {(() => {
                  const role = String(activeCamera.tuning_role);
                  const labelKey = cameraTuningRoleLabelKey(role);
                  return labelKey ? t(labelKey) : role;
                })()}
              </Typography>
            ) : null}
            <Typography variant="body2" color="text.secondary">
              {t('system.tuningWorkbenchCameraHint')}
            </Typography>
            <Stack direction="row" useFlexGap flexWrap="wrap" gap={1}>
              {CAMERA_TUNING_FIELD_DEFS.map((def) => (
                <TextField
                  key={def.key}
                  size="small"
                  sx={{ minWidth: 200, flex: '1 1 200px' }}
                  label={def.key}
                  value={draft[def.key] ?? ''}
                  onChange={(e) =>
                    setDraft((prev) => ({ ...prev, [def.key]: e.target.value }))
                  }
                />
              ))}
            </Stack>
            <Stack direction="row" spacing={1}>
              <Button
                variant="contained"
                size="small"
                disabled={mutating}
                onClick={() =>
                  saveCameraMutation.mutate({
                    cameraId: selectedCamera,
                    overrides: toOverrides(),
                  })
                }
              >
                {t('settings.save')}
              </Button>
              <Button
                variant="text"
                size="small"
                disabled={mutating}
                onClick={() =>
                  saveCameraMutation.mutate({
                    cameraId: selectedCamera,
                    overrides: {},
                  })
                }
              >
                {t('settings.reset', { defaultValue: 'Reset' })}
              </Button>
            </Stack>
            {activeCamera ? (
              <Typography variant="caption" color="text.secondary">
                Effective: R {activeCamera.effective.estimated_recall.toFixed(1)} · P{' '}
                {activeCamera.effective.estimated_precision.toFixed(1)} · Cost{' '}
                {activeCamera.effective.estimated_runtime_cost.toFixed(1)}
              </Typography>
            ) : null}
          </Stack>
        ) : null}

        <Divider />
        <Stack direction="row" spacing={1} alignItems="center">
          <Typography variant="subtitle2">{t('system.tuningWorkbenchAutoEval')}</Typography>
          {lastEval ? (
            <Chip
              size="small"
              color={lastEval.ok ? 'success' : 'warning'}
              label={lastEval.ok ? 'OK' : 'WARN'}
            />
          ) : null}
        </Stack>
        {lastEval ? (
          <Typography variant="caption" color="text.secondary">
            ΔR {fmtDelta(lastEval.delta.recall_delta)} · ΔP{' '}
            {fmtDelta(lastEval.delta.precision_delta)} · ΔCost{' '}
            {fmtDelta(lastEval.delta.runtime_cost_delta)}
          </Typography>
        ) : null}

        <Button
          variant="outlined"
          color="warning"
          size="small"
          disabled={mutating}
          onClick={() => rollbackMutation.mutate()}
        >
          {t('system.tuningWorkbenchRollback')}
        </Button>

        {applyPresetMutation.error || saveCameraMutation.error || rollbackMutation.error ? (
          <Alert severity="error" variant="outlined">
            {t('system.tuningWorkbenchMutationError')}
          </Alert>
        ) : null}
      </Stack>
    </SystemCardShell>
  );
}
