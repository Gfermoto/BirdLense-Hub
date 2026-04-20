import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import FormControl from '@mui/material/FormControl';
import Grid from '@mui/material/Grid2';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from './ServiceBlock';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

/** Реле/кнопка кормушки: feed.* */
export function FeederRelayFields({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.accordionFeed')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.accordionFeedDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="feed.source">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel id="settings-feed-type-label">
                  {t('settings.feedType')}
                </InputLabel>
                <Select
                  labelId="settings-feed-type-label"
                  value={field.state.value ?? 'none'}
                  label={t('settings.feedType')}
                  onChange={(e) => field.handleChange(e.target.value)}
                >
                  <MenuItem value="none">{t('settings.feedNone')}</MenuItem>
                  <MenuItem value="mqtt">{t('settings.feedMqtt')}</MenuItem>
                  <MenuItem value="esphome">{t('settings.feedEsp')}</MenuItem>
                </Select>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <form.Subscribe selector={(state) => state.values.feed?.source}>
          {(source) => (
            <>
              {source === 'mqtt' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.feedMqttHint')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.mqtt_topic">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.relayTopic')}
                          placeholder="cmnd/bird_feeder/Power"
                          helperText={t('settings.relayTopicHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
              {source === 'esphome' && (
                <>
                  <Grid size={{ xs: 12 }}>
                    <Alert severity="info" sx={{ mb: 2 }}>
                      {t('settings.esphomeFeedHint')}
                    </Alert>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_type">
                      {(field) => (
                        <FormControl fullWidth>
                          <InputLabel id="settings-switch-type-label">
                            {t('settings.switchType')}
                          </InputLabel>
                          <Select
                            labelId="settings-switch-type-label"
                            value={field.state.value ?? 'switch'}
                            label={t('settings.switchType')}
                            onChange={(e) =>
                              field.handleChange(
                                e.target.value as 'switch' | 'button',
                              )
                            }
                          >
                            <MenuItem value="switch">
                              {t('settings.switchTypeSwitch')}
                            </MenuItem>
                            <MenuItem value="button">
                              {t('settings.switchTypeButton')}
                            </MenuItem>
                          </Select>
                        </FormControl>
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_url">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.deviceUrl')}
                          placeholder="http://192.168.1.50"
                        />
                      )}
                    </form.Field>
                  </Grid>
                  <Grid size={{ xs: 12, sm: 6 }}>
                    <form.Field name="feed.esphome_switch_id">
                      {(field) => (
                        <TextField
                          fullWidth
                          value={field.state.value ?? ''}
                          onChange={(e) => field.handleChange(e.target.value)}
                          label={t('settings.switchId')}
                          placeholder="bird_feeder"
                          helperText={t('settings.switchIdHint')}
                        />
                      )}
                    </form.Field>
                  </Grid>
                </>
              )}
              {(source === 'mqtt' || source === 'esphome') && (
                <Grid size={{ xs: 12, sm: 6 }}>
                  <form.Field name="feed.duration_seconds">
                    {(field) => (
                      <TextField
                        fullWidth
                        type="number"
                        inputProps={{ min: 1, max: 30 }}
                        value={field.state.value ?? 3}
                        onChange={(e) =>
                          field.handleChange(Number(e.target.value) || 3)
                        }
                        label={t('settings.relaySeconds')}
                        helperText={t('settings.relaySecondsHint')}
                      />
                    )}
                  </form.Field>
                </Grid>
              )}
            </>
          )}
        </form.Subscribe>
      </Grid>
    </ServiceBlock>
  );
}
