import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import LinearProgress from '@mui/material/LinearProgress';
import Stack from '@mui/material/Stack';
import Typography from '@mui/material/Typography';
import {
  fetchRecognitionImprovementSummary,
  fetchRecognitionImprovementTrainStatus,
  getApiErrorMessage,
  rollbackRecognitionImprovement,
  startRecognitionImprovementTrain,
} from '../../api/api';
import { queryKeys } from '../../api/queryKeys';
import { SystemCardShell } from './SystemCardShell';

function formatTs(value?: string | null): string {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleString();
}

export function RecognitionImprovementCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [info, setInfo] = useState<string | null>(null);
  const [pollTraining, setPollTraining] = useState(false);

  const summaryQ = useQuery({
    queryKey: queryKeys.systemPanels.recognitionImprovementSummary,
    queryFn: fetchRecognitionImprovementSummary,
    staleTime: 10_000,
  });
  const trainingQ = useQuery({
    queryKey: queryKeys.systemPanels.recognitionImprovementTrainStatus,
    queryFn: fetchRecognitionImprovementTrainStatus,
    staleTime: 0,
    refetchInterval: (q) =>
      pollTraining || q.state.data?.status === 'running' ? 2_500 : false,
  });

  const trainMutation = useMutation({
    mutationFn: startRecognitionImprovementTrain,
    onSuccess: (data) => {
      setInfo(
        data.message ||
          t('system.recognitionImprovementTrainStarted', {
            defaultValue: 'Recognition improvement started',
          }),
      );
      setPollTraining(true);
    },
    onError: (error: unknown) => {
      setInfo(
        getApiErrorMessage(
          error,
          t('system.recognitionImprovementTrainFailed', {
            defaultValue: 'Could not start recognition improvement',
          }),
        ),
      );
    },
  });

  const rollbackMutation = useMutation({
    mutationFn: rollbackRecognitionImprovement,
    onSuccess: async () => {
      setInfo(
        t('system.recognitionImprovementRollbackDone', {
          defaultValue: 'Returned to the previous recognition mode',
        }),
      );
      await qc.invalidateQueries({
        queryKey: queryKeys.systemPanels.recognitionImprovementSummary,
      });
    },
    onError: (error: unknown) => {
      setInfo(
        getApiErrorMessage(
          error,
          t('system.recognitionImprovementRollbackFailed', {
            defaultValue: 'Could not roll back recognition mode',
          }),
        ),
      );
    },
  });

  useEffect(() => {
    if (!trainingQ.data?.status) return;
    if (trainingQ.data.status === 'running') {
      setPollTraining(true);
      return;
    }
    if (pollTraining) {
      setPollTraining(false);
      void qc.invalidateQueries({
        queryKey: queryKeys.systemPanels.recognitionImprovementSummary,
      });
    }
  }, [pollTraining, qc, trainingQ.data?.status]);

  const summary = summaryQ.data;
  const busy =
    trainMutation.isPending ||
    rollbackMutation.isPending ||
    trainingQ.data?.status === 'running';

  const activeModeLabel = useMemo(() => {
    switch (summary?.active_mode) {
      case 'disabled':
        return t('system.recognitionImprovementModeDisabled', {
          defaultValue: 'Improvement disabled',
        });
      case 'trained':
        return t('system.recognitionImprovementModeTrained', {
          defaultValue: 'Trained model active',
        });
      case 'heuristic':
      default:
        return t('system.recognitionImprovementModeHeuristic', {
          defaultValue: 'Built-in heuristic',
        });
    }
  }, [summary?.active_mode, t]);

  /** API `model.label` is English; show i18n mode text and only append an id for trained models. */
  const currentModeHumanLabel = useMemo(() => {
    if (summary?.active_mode !== 'trained') {
      return activeModeLabel;
    }
    const raw = String(summary.model.label || '').trim();
    const fallbackId = summary.model.active_model_id;
    const id =
      raw && !/^trained model$/i.test(raw)
        ? raw
        : fallbackId != null
          ? String(fallbackId).trim()
          : '';
    if (!id) return activeModeLabel;
    return `${activeModeLabel} (${id})`;
  }, [summary, activeModeLabel]);

  const statusTone =
    summary?.active_mode === 'trained'
      ? 'success'
      : summary?.active_mode === 'disabled'
        ? 'warning'
        : 'info';

  if (summaryQ.isLoading) {
    return (
      <Box
        role="status"
        aria-busy="true"
        aria-label={t('common.loading')}
        sx={{ py: 2, minWidth: 0 }}
      >
        <LinearProgress />
        <Typography
          variant="body2"
          color="text.secondary"
          sx={{ mt: 1.5 }}
        >
          {t('common.loading')}
        </Typography>
      </Box>
    );
  }

  if (summaryQ.isError || !summary) {
    return (
      <Alert severity="warning" variant="outlined">
        {t('system.recognitionImprovementLoadError', {
          defaultValue: 'Could not load recognition improvement status',
        })}
      </Alert>
    );
  }

  return (
    <SystemCardShell
      title={t('system.recognitionImprovementTitle', {
        defaultValue: 'Recognition improvement',
      })}
      description={t('system.recognitionImprovementDescription', {
        defaultValue:
          'Manual fixes from video pages are collected automatically. When there are enough examples, you can refresh the trained model without dealing with files or scripts.',
      })}
      statusLabel={activeModeLabel}
      statusTone={statusTone}
    >
      <Stack spacing={2}>
        {busy ? <LinearProgress aria-label={t('common.loading')} /> : null}
        {info ? (
          <Alert
            severity={trainingQ.data?.status === 'error' ? 'error' : 'info'}
            variant="outlined"
            onClose={() => setInfo(null)}
            role="status"
            aria-live="polite"
          >
            {info}
          </Alert>
        ) : null}
        {trainingQ.data?.error ? (
          <Alert severity="error" variant="outlined">
            {trainingQ.data.error}
          </Alert>
        ) : null}

        <Stack direction="row" flexWrap="wrap" gap={1}>
          <Chip
            size="small"
            color={summary.feedback.ready_for_training ? 'success' : 'default'}
            label={t('system.recognitionImprovementExamplesChip', {
              defaultValue: '{{count}} examples',
              count: summary.feedback.corrected_examples,
            })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.recognitionImprovementVideosChip', {
              defaultValue: '{{count}} videos',
              count: summary.feedback.unique_videos,
            })}
          />
          <Chip
            size="small"
            variant="outlined"
            label={t('system.recognitionImprovementSpeciesChip', {
              defaultValue: '{{count}} species',
              count: summary.feedback.unique_species,
            })}
          />
        </Stack>

        <Box>
          <Typography variant="body2" sx={{ mb: 0.75 }}>
            {t('system.recognitionImprovementCurrentMode', {
              defaultValue: 'Current mode',
            })}
            : <strong>{currentModeHumanLabel}</strong>
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {summary.feedback.ready_for_training
              ? t('system.recognitionImprovementReadyText', {
                  defaultValue:
                    'There are enough corrected examples to train and activate a new model.',
                })
              : t('system.recognitionImprovementNeedMoreText', {
                  defaultValue:
                    'Need {{count}} more corrected examples before training is recommended.',
                  count: summary.feedback.examples_until_ready,
                })}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
            {t('system.recognitionImprovementLastTraining', {
              defaultValue: 'Last training',
            })}
            : {formatTs(summary.model.last_trained_at)}
          </Typography>
          <Typography variant="body2" color="text.secondary">
            {t('system.recognitionImprovementLastFeedback', {
              defaultValue: 'Last manual fix',
            })}
            : {formatTs(summary.feedback.latest_feedback_at)}
          </Typography>
        </Box>

        <Stack spacing={1.25} alignItems="flex-start">
          <Stack direction={{ xs: 'column', sm: 'row' }} flexWrap="wrap" gap={1}>
            <Button
              variant="contained"
              disabled={busy || !summary.feedback.ready_for_training}
              onClick={() => trainMutation.mutate()}
            >
              {t('system.recognitionImprovementUpdateModel', {
                defaultValue: 'Update model',
              })}
            </Button>
            <Button
              variant="outlined"
              color="warning"
              disabled={busy || !summary.model.can_roll_back}
              onClick={() => rollbackMutation.mutate()}
            >
              {t('system.recognitionImprovementRollback', {
                defaultValue: 'Roll back',
              })}
            </Button>
          </Stack>
          <Typography variant="caption" color="text.secondary" sx={{ maxWidth: 720 }}>
            {t('system.recognitionImprovementActionsHint')}
          </Typography>
        </Stack>
      </Stack>
    </SystemCardShell>
  );
}
