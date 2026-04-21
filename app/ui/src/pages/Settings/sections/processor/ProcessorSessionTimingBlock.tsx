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
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.min_seconds_between_recordings">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 300, step: 1 }}
                value={field.state.value ?? 8}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.minSecondsBetweenRecordings')}
                helperText={t('settings.minSecondsBetweenRecordingsHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.file_max_record_floor_seconds">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 60, max: 172800, step: 60 }}
                value={field.state.value ?? 86400}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 86400)
                }
                label={t('settings.fileMaxRecordFloorSeconds')}
                helperText={t('settings.fileMaxRecordFloorSecondsHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.frigate_activity_hold_seconds">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 120, step: 1 }}
                value={field.state.value ?? 6}
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.frigateActivityHoldSeconds')}
                helperText={t('settings.frigateActivityHoldSecondsHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
