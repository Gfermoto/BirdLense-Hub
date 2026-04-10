import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PasswordField } from '../../../components/PasswordField';
import { ServiceBlock } from '../shared/ServiceBlock';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function IntegrationsSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionIntegrations')}
      </AccordionSummary>
      <AccordionDetails>
        <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
          <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
            {t('settings.accordionIntegrations')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionIntegrationsDesc')}
          </Typography>

          <ServiceBlock title={t('settings.serviceXenoCanto')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="secrets.xeno_canto_api_key">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.xenoCantoApiKey')}
                      helperText={t('settings.xenoCantoApiKeyHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title="MCP">
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="mcp.enabled">
                  {(field) => (
                    <>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value ?? false}
                            onChange={(e) => field.handleChange(e.target.checked)}
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
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
