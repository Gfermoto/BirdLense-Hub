import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PasswordField } from '../../../components/PasswordField';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function HomeAssistantSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionHomeAssistant')}
      </AccordionSummary>
      <AccordionDetails>
        <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
          <Box
            component="legend"
            sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}
          >
            {t('settings.accordionHomeAssistant')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionHomeAssistantDesc')}
          </Typography>
          <Alert severity="info" sx={{ mb: 2 }}>
            {t('settings.haEnvOverrideHint')}
          </Alert>
          <Grid container spacing={2}>
            <Grid size={{ xs: 12 }}>
              <form.Field name="homeassistant.url">
                {(field) => (
                  <TextField
                    fullWidth
                    value={field.state.value ?? ''}
                    onChange={(e) => field.handleChange(e.target.value)}
                    label={t('settings.haUrl')}
                    placeholder="http://homeassistant:8123"
                    helperText={t('settings.haUrlHint')}
                  />
                )}
              </form.Field>
            </Grid>
            <Grid size={{ xs: 12 }}>
              <form.Field name="homeassistant.token">
                {(field) => (
                  <PasswordField
                    value={field.state.value ?? ''}
                    onChange={(v) => field.handleChange(v)}
                    label={t('settings.haToken')}
                    placeholder={t('settings.haTokenPlaceholder')}
                    helperText={t('settings.haTokenHint')}
                  />
                )}
              </form.Field>
            </Grid>
          </Grid>
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
