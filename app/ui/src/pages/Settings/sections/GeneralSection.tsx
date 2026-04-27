import { useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useQueryClient } from '@tanstack/react-query';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import Accordion from '@mui/material/Accordion';
import AccordionDetails from '@mui/material/AccordionDetails';
import AccordionSummary from '@mui/material/AccordionSummary';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Stack from '@mui/material/Stack';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControl from '@mui/material/FormControl';
import { PasswordField } from '../../../components/PasswordField';
import {
  downloadSettingsYamlFull,
  downloadSettingsYamlSafe,
  fetchCoordinatesByZip,
  importSettingsYaml,
} from '../../../api/settingsYamlDb';
import { queryKeys } from '../../../api/queryKeys';
import type { Settings } from '../../../types';
import { ServiceBlock } from '../shared/ServiceBlock';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  /** Маскированный YAML — оператор и админ */
  yamlSafeExportEnabled?: boolean;
  /** Полный YAML и импорт — только админ (при двух паролях) */
  yamlAdminBackupEnabled?: boolean;
};

export function GeneralSection({
  form,
  yamlSafeExportEnabled = false,
  yamlAdminBackupEnabled = false,
}: Props) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);
  const [yamlMsg, setYamlMsg] = useState<{
    sev: 'success' | 'error';
    text: string;
  } | null>(null);

  const handleZipLookup = async () => {
    const zip = form.getFieldValue('secrets.zip');
    if (!zip) return;
    try {
      const { lat, lon } = await fetchCoordinatesByZip(zip);
      form.setFieldValue('secrets.latitude', lat);
      form.setFieldValue('secrets.longitude', lon);
    } catch (error) {
      console.log(error);
      alert(t('settings.zipFetchFailed'));
    }
  };

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionGeneral')}
      </AccordionSummary>
      <AccordionDetails>
        <Box
          component="fieldset"
          sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}
        >
          <Box
            component="legend"
            sx={{
              clip: 'rect(0,0,0,0)',
              position: 'absolute',
              width: 1,
              height: 1,
              overflow: 'hidden',
            }}
          >
            {t('settings.accordionGeneral')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionGeneralDesc')}
          </Typography>

          <ServiceBlock title={t('settings.serviceSystem')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="general.donate_url">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.donateUrl')}
                      placeholder="https://ko-fi.com/..."
                      helperText={t('settings.donateUrlHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceWeatherLocation')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="weather.source">
                  {(field) => (
                    <FormControl fullWidth>
                      <InputLabel id="settings-weather-source-label">
                        {t('settings.weatherSource')}
                      </InputLabel>
                      <Select
                        labelId="settings-weather-source-label"
                        value={field.state.value ?? 'openweather'}
                        label={t('settings.weatherSource')}
                        onChange={(e) =>
                          field.handleChange(
                            e.target.value as 'openweather' | 'homeassistant',
                          )
                        }
                      >
                        <MenuItem value="openweather">
                          {t('settings.weatherOpenWeather')}
                        </MenuItem>
                        <MenuItem value="homeassistant">
                          {t('settings.weatherHomeAssistant')}
                        </MenuItem>
                      </Select>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <form.Subscribe
                selector={(state) => state.values.weather?.source}
              >
                {(source) => (
                  <>
                    {source !== 'homeassistant' && (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="secrets.openweather_api_key">
                            {(field) => (
                              <PasswordField
                                value={field.state.value ?? ''}
                                onChange={(v) => field.handleChange(v)}
                                label={t('settings.openWeatherApiKey')}
                                helperText={t('settings.weatherHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <form.Field name="secrets.zip">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.zip')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <Button
                            fullWidth
                            variant="outlined"
                            onClick={handleZipLookup}
                          >
                            {t('settings.zipLookup')}
                          </Button>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <form.Field name="secrets.latitude">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(
                                    (e.target.value ?? '').replace(',', '.'),
                                  )
                                }
                                label={t('settings.latitude')}
                                helperText={t('settings.latitudeHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                        <Grid size={{ xs: 6 }}>
                          <form.Field name="secrets.longitude">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(
                                    (e.target.value ?? '').replace(',', '.'),
                                  )
                                }
                                label={t('settings.longitude')}
                                helperText={t('settings.longitudeHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                    {source === 'homeassistant' && (
                      <>
                        <Grid size={{ xs: 12 }}>
                          <Alert
                            severity="info"
                            variant="outlined"
                            sx={{ mb: 2 }}
                          >
                            {t('settings.weatherHaAlert')}
                          </Alert>
                        </Grid>
                        <Grid size={{ xs: 12 }}>
                          <form.Field name="weather.ha_entity_id">
                            {(field) => (
                              <TextField
                                fullWidth
                                value={field.state.value ?? ''}
                                onChange={(e) =>
                                  field.handleChange(e.target.value)
                                }
                                label={t('settings.weatherHaEntity')}
                                placeholder="weather.home"
                                helperText={t('settings.weatherHaEntityHint')}
                              />
                            )}
                          </form.Field>
                        </Grid>
                      </>
                    )}
                  </>
                )}
              </form.Subscribe>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceMcp')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="mcp.enabled">
                  {(field) => (
                    <>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value ?? false}
                            onChange={(e) =>
                              field.handleChange(e.target.checked)
                            }
                          />
                        }
                        label={t('settings.mcpEnabled')}
                      />
                      <FormHelperText>{t('settings.mcpHint')}</FormHelperText>
                    </>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="mcp.token">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.mcpToken')}
                      placeholder={t('settings.mcpTokenPlaceholder')}
                      helperText={t('settings.mcpTokenHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.accordionPerformance')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="performance.cache_redis_enabled">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value !== false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.performanceRedisEnabled')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.performanceRedisEnabledHint')}
                </FormHelperText>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Subscribe
                  selector={(s) =>
                    s.values.performance?.redis_url_effective_masked ?? ''
                  }
                >
                  {(effectiveMasked) => (
                    <form.Field name="performance.redis_url">
                      {(field) => {
                        const raw = (field.state.value ?? '').trim();
                        const placeholder =
                          !raw && effectiveMasked
                            ? effectiveMasked
                            : 'redis://redis:6379/0';

                        return (
                          <TextField
                            fullWidth
                            value={field.state.value ?? ''}
                            onChange={(e) => field.handleChange(e.target.value)}
                            label={t('settings.performanceRedisUrl')}
                            placeholder={placeholder}
                            helperText={
                              <>
                                <Box component="span" display="block">
                                  {t('settings.performanceRedisUrlHint')}
                                </Box>
                                {effectiveMasked ? (
                                  <Box
                                    component="span"
                                    display="block"
                                    sx={{ mt: 0.5 }}
                                  >
                                    {t(
                                      'settings.performanceRedisEffectiveNow',
                                      {
                                        url: effectiveMasked,
                                      },
                                    )}
                                  </Box>
                                ) : null}
                              </>
                            }
                          />
                        );
                      }}
                    </form.Field>
                  )}
                </form.Subscribe>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.accordionSecurity')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="general.settings_password">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.settingsPassword')}
                      placeholder={t('settings.settingsPasswordPlaceholder')}
                      helperText={t('settings.settingsPasswordHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="general.contributor_password">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.contributorPassword')}
                      placeholder={t('settings.contributorPasswordPlaceholder')}
                      helperText={t('settings.contributorPasswordHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="general.session_idle_minutes">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 10080, step: 1 }}
                      value={field.state.value ?? 30}
                      onChange={(e) => {
                        const raw = e.target.value;
                        const n = raw === '' ? 0 : Number(raw);
                        const clamped = Number.isFinite(n)
                          ? Math.max(0, Math.min(10080, Math.trunc(n)))
                          : 30;
                        field.handleChange(clamped);
                      }}
                      label={t('settings.sessionIdleMinutes')}
                      helperText={t('settings.sessionIdleMinutesHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          {yamlSafeExportEnabled || yamlAdminBackupEnabled ? (
            <ServiceBlock title={t('settings.yamlBackupTitle')}>
              <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                {yamlAdminBackupEnabled
                  ? t('settings.yamlBackupDesc')
                  : t('settings.yamlBackupDescSafeOnly')}
              </Typography>
              {yamlMsg ? (
                <Alert
                  severity={yamlMsg.sev}
                  variant="outlined"
                  sx={{ mb: 2 }}
                  onClose={() => setYamlMsg(null)}
                >
                  {yamlMsg.text}
                </Alert>
              ) : null}
              <Stack direction="row" flexWrap="wrap" gap={1} useFlexGap>
                {yamlSafeExportEnabled ? (
                  <Button
                    variant="outlined"
                    size="small"
                    onClick={async () => {
                      setYamlMsg(null);
                      try {
                        await downloadSettingsYamlSafe();
                      } catch (e) {
                        setYamlMsg({
                          sev: 'error',
                          text:
                            e instanceof Error
                              ? e.message
                              : t('settings.yamlImportFailed'),
                        });
                      }
                    }}
                  >
                    {t('settings.yamlDownloadSafe')}
                  </Button>
                ) : null}
                {yamlAdminBackupEnabled ? (
                  <>
                    <Button
                      variant="outlined"
                      size="small"
                      color="warning"
                      onClick={async () => {
                        if (!window.confirm(t('settings.yamlFullConfirm')))
                          return;
                        setYamlMsg(null);
                        try {
                          await downloadSettingsYamlFull();
                        } catch (e) {
                          setYamlMsg({
                            sev: 'error',
                            text:
                              e instanceof Error
                                ? e.message
                                : t('settings.yamlImportFailed'),
                          });
                        }
                      }}
                    >
                      {t('settings.yamlDownloadFull')}
                    </Button>
                    <Button
                      variant="outlined"
                      size="small"
                      onClick={() => fileRef.current?.click()}
                    >
                      {t('settings.yamlImport')}
                    </Button>
                    <input
                      ref={fileRef}
                      type="file"
                      accept=".yaml,.yml,text/yaml"
                      hidden
                      onChange={async (ev) => {
                        const f = ev.target.files?.[0];
                        ev.target.value = '';
                        if (!f) return;
                        setYamlMsg(null);
                        const r = await importSettingsYaml(f);
                        if (r.ok) {
                          setYamlMsg({
                            sev: 'success',
                            text: r.message || t('settings.yamlImportOk'),
                          });
                          await queryClient.invalidateQueries({
                            queryKey: queryKeys.settings.all,
                          });
                        } else {
                          setYamlMsg({
                            sev: 'error',
                            text: r.message || t('settings.yamlImportFailed'),
                          });
                        }
                      }}
                    />
                  </>
                ) : null}
              </Stack>
            </ServiceBlock>
          ) : null}
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
