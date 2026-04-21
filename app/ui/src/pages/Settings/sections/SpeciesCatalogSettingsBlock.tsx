import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { ServiceBlock } from '../shared/ServiceBlock';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

function parseSpeciesIdList(raw: string): number[] {
  return (raw || '')
    .split(/[,\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
    .map((s) => parseInt(s, 10))
    .filter((n) => Number.isFinite(n));
}

/** species.* — строгий ingest, цели дообучения (путь allowlist — только YAML). */
export function SpeciesCatalogSettingsBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
    <ServiceBlock title={t('settings.speciesCatalogTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.speciesCatalogDesc')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="species.catalog_strict_ingest">
            {(field) => (
              <>
                <FormControlLabel
                  control={
                    <Switch
                      checked={field.state.value !== false}
                      onChange={(e) => field.handleChange(e.target.checked)}
                    />
                  }
                  label={t('settings.speciesCatalogStrictIngest')}
                />
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.speciesCatalogStrictIngestHint')}
                </FormHelperText>
              </>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="species.tuning_target_species_ids">
            {(field) => (
              <TextField
                fullWidth
                value={(field.state.value ?? []).join(', ')}
                onChange={(e) =>
                  field.handleChange(parseSpeciesIdList(e.target.value))
                }
                label={t('settings.speciesTuningTargetIds')}
                helperText={t('settings.speciesTuningTargetIdsHint')}
                placeholder="1, 2, 3"
              />
            )}
          </form.Field>
        </Grid>
      </Grid>
    </ServiceBlock>
  );
}
