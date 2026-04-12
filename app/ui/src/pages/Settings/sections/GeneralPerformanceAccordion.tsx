import React from 'react';
import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import type { Settings } from '../../../types';

type Props = { form: ReactFormExtendedApi<Settings, undefined> };

export function GeneralPerformanceAccordion({ form }: Props) {
  const { t } = useTranslation();
  return (
      <Accordion>
        <AccordionSummary expandIcon={<ExpandMoreIcon />}>
          {t('settings.accordionPerformance')}
        </AccordionSummary>
        <AccordionDetails>
          <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.accordionPerformanceDesc')}
            </Typography>
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
                  selector={(s) => s.values.performance?.redis_url_effective_masked ?? ''}
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
                                  <Box component="span" display="block" sx={{ mt: 0.5 }}>
                                    {t('settings.performanceRedisEffectiveNow', {
                                      url: effectiveMasked,
                                    })}
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
          </Box>
        </AccordionDetails>
      </Accordion>
  );
}
