import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import Alert from '@mui/material/Alert';
import Button from '@mui/material/Button';
import Stack from '@mui/material/Stack';
import { getApiErrorMessage } from '../../api/api';
import { startBehaviorBaselineRetrainFromHub } from '../../api/speciesRegistryHub';
import { SystemCardShell } from './SystemCardShell';

export function BehaviorBaselineRetrainCard() {
  const { t } = useTranslation();
  const [info, setInfo] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: startBehaviorBaselineRetrainFromHub,
    onSuccess: (data) => {
      const n = data.n_training_videos ?? 0;
      const labels = (data.labels || []).join(', ');
      const path = data.export_path || '—';
      setInfo(
        t('system.behaviorBaselineRetrainSuccess', {
          count: n,
          labels,
          path,
        }),
      );
    },
    onError: (error: unknown) => {
      setInfo(
        getApiErrorMessage(
          error,
          t('system.behaviorBaselineRetrainFailed', {
            defaultValue: 'Could not retrain behavior baseline',
          }),
        ),
      );
    },
  });

  return (
    <SystemCardShell
      id="behavior-baseline-retrain"
      title={t('system.behaviorBaselineRetrainTitle')}
      description={t('system.behaviorBaselineRetrainDescription')}
      actions={
        <Button
          variant="contained"
          color="primary"
          disabled={mutation.isPending}
          onClick={() => {
            setInfo(null);
            mutation.mutate();
          }}
        >
          {t('system.behaviorBaselineRetrainButton')}
        </Button>
      }
    >
      <Stack spacing={1.5}>
        {info ? (
          <Alert
            severity={mutation.isError ? 'error' : 'success'}
            variant="outlined"
            onClose={() => setInfo(null)}
          >
            {info}
          </Alert>
        ) : null}
      </Stack>
    </SystemCardShell>
  );
}
