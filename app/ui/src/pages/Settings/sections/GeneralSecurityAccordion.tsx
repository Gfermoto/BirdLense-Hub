import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PasswordField } from '../../../components/PasswordField';
import type { Settings } from '../../../types';

type Props = { form: ReactFormExtendedApi<Settings, undefined> };

export function GeneralSecurityAccordion({ form }: Props) {
  const { t } = useTranslation();
  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionSecurity')}
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
            {t('settings.accordionSecurity')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionSecurityDesc')}
          </Typography>
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
            <Grid size={{ xs: 12 }}>
              <form.Field name="general.require_auth_for_video_stream">
                {(field) => (
                  <>
                    <FormControlLabel
                      control={
                        <Switch
                          checked={Boolean(field.state.value)}
                          onChange={(e) =>
                            field.handleChange(e.target.checked)
                          }
                        />
                      }
                      label={t('settings.requireAuthVideoStream')}
                    />
                    <Typography
                      variant="body2"
                      color="text.secondary"
                      display="block"
                    >
                      {t('settings.requireAuthVideoStreamHint')}
                    </Typography>
                  </>
                )}
              </form.Field>
            </Grid>
          </Grid>
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
