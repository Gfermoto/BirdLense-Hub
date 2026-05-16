import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import Checkbox from '@mui/material/Checkbox';
import Divider from '@mui/material/Divider';
import FormControlLabel from '@mui/material/FormControlLabel';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { FrigateExclusionsFields } from './FrigateExclusionsFields';
import type { Settings } from '../../../types';

function splitCsv(value: string): string[] {
  return (value || '')
    .split(',')
    .map((part) => part.trim())
    .filter(Boolean);
}

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

/** External MQTT detector trigger: threshold, allow lists, exclusions. Topic lives under Connections → MQTT. */
export function FrigateTriggerBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <>
      <form.Field name="triggers.frigate.enabled">
        {(field) => (
          <FormControlLabel
            control={
              <Checkbox
                checked={field.state.value !== false}
                onChange={(e) => field.handleChange(e.target.checked)}
              />
            }
            label={t('settings.triggerFrigate')}
          />
        )}
      </form.Field>

      <form.Subscribe
        selector={(state) => state.values.triggers?.frigate?.enabled !== false}
      >
        {(enabled) =>
          enabled ? (
            <>
              <Alert severity="info" variant="outlined" sx={{ mt: 2, mb: 2 }}>
                {t('settings.frigateMotionIntro')}
              </Alert>

              <Typography variant="subtitle2" sx={{ mb: 1 }}>
                {t('settings.frigateThresholdHeading')}
              </Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="triggers.frigate.min_trigger_score">
                    {(field) => (
                      <TextField
                        fullWidth
                        type="number"
                        inputProps={{ min: 0, max: 1, step: 0.05 }}
                        value={
                          field.state.value === undefined ||
                          field.state.value === null
                            ? 0.5
                            : field.state.value
                        }
                        onChange={(e) => {
                          const v = e.target.value;
                          if (v === '') {
                            field.handleChange(undefined);
                            return;
                          }
                          field.handleChange(Number(v));
                        }}
                        label={t('settings.frigateMinTriggerScore')}
                        helperText={t('settings.frigateMinTriggerScoreHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              </Grid>

              <Divider sx={{ my: 2 }} />

              <Typography variant="subtitle2" sx={{ mb: 0.5 }}>
                {t('settings.frigateRoutingTitle')}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 1.5 }}
              >
                {t('settings.frigateRoutingDesc')}
              </Typography>
              <Grid container spacing={2} sx={{ mb: 2 }}>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="triggers.frigate.camera_filter">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={(field.state.value || []).join(', ')}
                        onChange={(e) =>
                          field.handleChange(splitCsv(e.target.value))
                        }
                        label={t('settings.frigateCameraFilter')}
                        placeholder={t('settings.frigateCameraFilterPlaceholder')}
                        helperText={t('settings.frigateCameraFilterHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="triggers.frigate.label_filter">
                    {(field) => (
                      <TextField
                        fullWidth
                        value={(field.state.value || []).join(', ')}
                        onChange={(e) =>
                          field.handleChange(splitCsv(e.target.value))
                        }
                        label={t('settings.frigateLabelFilter')}
                        placeholder={t('settings.frigateLabelFilterPlaceholder')}
                        helperText={t('settings.frigateLabelFilterHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              </Grid>

              <Divider sx={{ my: 2 }} />

              <FrigateExclusionsFields form={form} />
            </>
          ) : null
        }
      </form.Subscribe>
    </>
  );
}
