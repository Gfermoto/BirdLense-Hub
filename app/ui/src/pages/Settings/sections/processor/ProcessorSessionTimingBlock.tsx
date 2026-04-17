import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorSessionTimingBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.serviceProcessor')}>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.max_record_seconds">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                value={field.state.value ?? 60}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                label={t('settings.maxRecordSeconds')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.max_inactive_seconds">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                value={field.state.value ?? 10}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                label={t('settings.inactiveSeconds')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.min_track_duration">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                value={field.state.value ?? 1}
                onChange={(e) => field.handleChange(Number(e.target.value))}
                label={t('settings.minTrackDuration')}
                helperText={t('settings.minTrackDurationHelp')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.min_box_size_px">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 16, max: 256, step: 1 }}
                value={field.state.value ?? 64}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
                label={t('settings.minBoxSizePx')}
                helperText={t('settings.minBoxSizePxHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.post_record_seconds">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 120, step: 1 }}
                value={field.state.value ?? 0}
                onChange={(e) =>
                  field.handleChange(
                    Math.max(0, Math.min(120, Number(e.target.value) || 0)),
                  )
                }
                label={t('settings.postRecordSeconds')}
                helperText={t('settings.postRecordSecondsHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
