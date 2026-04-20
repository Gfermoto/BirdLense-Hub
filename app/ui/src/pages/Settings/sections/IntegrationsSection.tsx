import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import axios from 'axios';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import CircularProgress from '@mui/material/CircularProgress';
import Grid from '@mui/material/Grid2';
import Table from '@mui/material/Table';
import TableBody from '@mui/material/TableBody';
import TableCell from '@mui/material/TableCell';
import TableHead from '@mui/material/TableHead';
import TableRow from '@mui/material/TableRow';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { PasswordField } from '../../../components/PasswordField';
import { ServiceBlock } from '../shared/ServiceBlock';
import { SpeciesCatalogSettingsBlock } from './SpeciesCatalogSettingsBlock';
import type { Settings } from '../../../types';
import {
  fetchEbirdMappingSuggestions,
  type EbirdMappingSuggestionsResponse,
} from '../../../api/api';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function IntegrationsSection({ form }: Props) {
  const { t } = useTranslation();
  const [ebirdSuggestLoading, setEbirdSuggestLoading] = useState(false);
  const [ebirdSuggestError, setEbirdSuggestError] = useState<string | null>(
    null,
  );
  const [ebirdSuggestData, setEbirdSuggestData] =
    useState<EbirdMappingSuggestionsResponse | null>(null);

  const loadEbirdMappingSuggestions = async () => {
    setEbirdSuggestLoading(true);
    setEbirdSuggestError(null);
    try {
      const data = await fetchEbirdMappingSuggestions();
      setEbirdSuggestData(data);
    } catch (err: unknown) {
      let msg = t('settings.ebirdMappingSuggestFailed');
      if (axios.isAxiosError(err)) {
        const d = err.response?.data as { error?: string } | undefined;
        if (d?.error) msg = d.error;
        else if (err.message) msg = err.message;
      } else if (err instanceof Error && err.message) {
        msg = err.message;
      }
      setEbirdSuggestError(msg);
    } finally {
      setEbirdSuggestLoading(false);
    }
  };

  const applyEbirdMappingSuggestion = (
    ebirdName: string,
    birdlenseName: string,
  ) => {
    const cur = form.getFieldValue('ebird.species_mapping');
    const base =
      cur && typeof cur === 'object' && !Array.isArray(cur) ? { ...cur } : {};
    base[ebirdName] = birdlenseName;
    form.setFieldValue('ebird.species_mapping', base);
  };

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionIntegrations')}
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
            {t('settings.accordionIntegrations')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionIntegrationsDesc')}
          </Typography>

          <ServiceBlock title={t('settings.serviceEbird')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="secrets.ebird_api_key">
                  {(field) => (
                    <PasswordField
                      value={field.state.value ?? ''}
                      onChange={(v) => field.handleChange(v)}
                      label={t('settings.ebirdApiKey')}
                      helperText={t('settings.ebirdApiKeyHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <Typography
                  variant="body2"
                  color="text.secondary"
                  sx={{ mb: 1 }}
                >
                  {t('settings.ebirdSection')}
                </Typography>
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                  <form.Field name="ebird.country">
                    {(field) => (
                      <TextField
                        sx={{ minWidth: 100, flex: 1 }}
                        size="small"
                        value={field.state.value ?? ''}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.ebirdCountry')}
                        placeholder="US"
                        helperText={t('settings.ebirdCountryHint')}
                      />
                    )}
                  </form.Field>
                  <form.Field name="ebird.state">
                    {(field) => (
                      <TextField
                        sx={{ minWidth: 100, flex: 1 }}
                        size="small"
                        value={field.state.value ?? ''}
                        onChange={(e) => field.handleChange(e.target.value)}
                        label={t('settings.ebirdState')}
                        placeholder="NY"
                        helperText={t('settings.ebirdStateHint')}
                      />
                    )}
                  </form.Field>
                </Box>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="ebird.location_name">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.ebirdLocation')}
                      helperText={t('settings.ebirdLocationHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="ebird.species_mapping">
                  {(field) => {
                    const val = field.state.value;
                    const str =
                      val && typeof val === 'object' && !Array.isArray(val)
                        ? Object.entries(val)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join('\n')
                        : '';
                    return (
                      <TextField
                        fullWidth
                        multiline
                        minRows={2}
                        value={str}
                        onChange={(e) => {
                          const lines = e.target.value
                            .split('\n')
                            .filter(Boolean);
                          const obj: Record<string, string> = {};
                          for (const line of lines) {
                            const idx = line.indexOf(':');
                            if (idx > 0) {
                              const k = line.slice(0, idx).trim();
                              const v = line.slice(idx + 1).trim();
                              if (k && v) obj[k] = v;
                            }
                          }
                          field.handleChange(
                            Object.keys(obj).length ? obj : {},
                          );
                        }}
                        label={t('settings.ebirdSpeciesMapping')}
                        placeholder="Gray-headed Woodpecker: Grey-headed Woodpecker"
                        helperText={t('settings.ebirdSpeciesMappingHint')}
                      />
                    );
                  }}
                </form.Field>
                <Box
                  sx={{
                    mt: 1.5,
                    display: 'flex',
                    alignItems: 'center',
                    gap: 1,
                    flexWrap: 'wrap',
                  }}
                >
                  <Button
                    type="button"
                    variant="outlined"
                    size="small"
                    disabled={ebirdSuggestLoading}
                    onClick={loadEbirdMappingSuggestions}
                    startIcon={
                      ebirdSuggestLoading ? (
                        <CircularProgress size={14} color="inherit" />
                      ) : undefined
                    }
                  >
                    {t('settings.ebirdMappingSuggestLoad')}
                  </Button>
                  {ebirdSuggestData && ebirdSuggestData.ebird_api_configured ? (
                    <Typography variant="caption" color="text.secondary">
                      {t('settings.ebirdMappingSuggestRegion', {
                        region: ebirdSuggestData.region_code,
                        count: ebirdSuggestData.top_count,
                      })}
                    </Typography>
                  ) : null}
                </Box>
                {ebirdSuggestError ? (
                  <Alert severity="error" sx={{ mt: 1 }}>
                    {ebirdSuggestError}
                  </Alert>
                ) : null}
                {ebirdSuggestData && !ebirdSuggestData.ebird_api_configured ? (
                  <Alert severity="info" sx={{ mt: 1 }}>
                    {t('settings.ebirdMappingSuggestNoKey')}
                  </Alert>
                ) : null}
                {ebirdSuggestData &&
                ebirdSuggestData.ebird_api_configured &&
                ebirdSuggestData.suggestions.length > 0 ? (
                  <Table size="small" sx={{ mt: 1.5 }}>
                    <TableHead>
                      <TableRow>
                        <TableCell>
                          {t('settings.ebirdMappingColEbird')}
                        </TableCell>
                        <TableCell>
                          {t('settings.ebirdMappingColBirdlense')}
                        </TableCell>
                        <TableCell align="right">
                          {t('settings.ebirdMappingColAction')}
                        </TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {ebirdSuggestData.suggestions.map((row) => (
                        <TableRow key={row.ebird_name}>
                          <TableCell>{row.ebird_name}</TableCell>
                          <TableCell>
                            {row.birdlense_name ?? '—'}
                            {row.kind === 'fuzzy' && row.score != null ? (
                              <Typography
                                component="span"
                                variant="caption"
                                color="text.secondary"
                                sx={{ ml: 0.5 }}
                              >
                                ({row.score})
                              </Typography>
                            ) : null}
                          </TableCell>
                          <TableCell align="right">
                            {row.birdlense_name ? (
                              <Button
                                type="button"
                                size="small"
                                onClick={() =>
                                  applyEbirdMappingSuggestion(
                                    row.ebird_name,
                                    row.birdlense_name as string,
                                  )
                                }
                              >
                                {t('settings.ebirdMappingApply')}
                              </Button>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                ) : null}
                {ebirdSuggestData &&
                ebirdSuggestData.ebird_api_configured &&
                ebirdSuggestData.suggestions.length === 0 ? (
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mt: 1 }}
                  >
                    {t('settings.ebirdMappingSuggestEmpty')}
                  </Typography>
                ) : null}
              </Grid>
            </Grid>
          </ServiceBlock>

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

          <ServiceBlock title={t('settings.serviceBirdnet')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="general.birdnet_url">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.birdnetUrl')}
                      placeholder="http://birdnet.local"
                      helperText={t('settings.birdnetUrlHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="integrations.birdnet.mqtt_topic">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? 'birdnet'}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.birdnetTopic')}
                      placeholder="birdnet"
                      helperText={t('settings.birdnetTopicHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <SpeciesCatalogSettingsBlock form={form} />
        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
