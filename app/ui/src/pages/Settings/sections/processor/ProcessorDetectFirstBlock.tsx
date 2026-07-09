import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

function NumField({
  form,
  name,
  label,
  helperText,
  min,
  max,
  step,
}: {
  form: ReactFormExtendedApi<Settings, undefined>;
  name: string;
  label: string;
  helperText?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <form.Field name={name as never}>
      {(field) => (
        <TextField
          fullWidth
          size="small"
          type="number"
          label={label}
          helperText={helperText}
          value={field.state.value ?? ''}
          onChange={(e) => {
            const raw = e.target.value.trim();
            field.handleChange((raw === '' ? undefined : Number(raw)) as never);
          }}
          inputProps={{ min, max, step }}
        />
      )}
    </form.Field>
  );
}

export function ProcessorDetectFirstBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.processorDetectFirstTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.processorDetectFirstDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.detect_first_enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.processorDetectFirstEnabled')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <NumField
            form={form}
            name="processor.detect_first_window_seconds"
            label={t('settings.processorDetectFirstWindowSeconds')}
            helperText={t('settings.processorDetectFirstWindowSecondsHint')}
            min={0.2}
            max={30}
            step={0.1}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <NumField
            form={form}
            name="processor.detect_first_max_frames"
            label={t('settings.processorDetectFirstMaxFrames')}
            min={1}
            max={300}
            step={1}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <NumField
            form={form}
            name="processor.detect_first_confirm_min_hits"
            label={t('settings.processorDetectFirstConfirmMinHits')}
            helperText={t('settings.processorDetectFirstConfirmMinHitsHint')}
            min={1}
            max={10}
            step={1}
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <NumField
            form={form}
            name="processor.detect_first_confirm_min_track_seconds"
            label={t('settings.processorDetectFirstConfirmMinTrackSeconds')}
            min={0}
            max={30}
            step={0.05}
          />
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
