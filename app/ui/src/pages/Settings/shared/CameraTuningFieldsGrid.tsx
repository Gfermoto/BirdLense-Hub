import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import { CAMERA_TUNING_FIELD_DEFS } from '../shared/cameraTuningFields';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
  /** e.g. processor.camera_overrides.BirdBox */
  namePrefix: string;
};

export function CameraTuningFieldsGrid({ form, namePrefix }: Props) {
  const { t } = useTranslation();

  return (
    <Grid container spacing={2}>
      {CAMERA_TUNING_FIELD_DEFS.map((def) => {
        const fieldName = `${namePrefix}.${def.key}`;
        return (
          <Grid key={def.key} size={{ xs: 12, sm: 6, md: 4 }}>
            <form.Field name={fieldName as never}>
              {(field) => {
                if (def.kind === 'boolean') {
                  return (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={Boolean(field.state.value)}
                          onChange={(e) => field.handleChange(e.target.checked as never)}
                        />
                      }
                      label={t(def.labelKey)}
                    />
                  );
                }
                return (
                  <TextField
                    fullWidth
                    size="small"
                    type="number"
                    value={field.state.value ?? ''}
                    onChange={(e) => {
                      const raw = e.target.value.trim();
                      field.handleChange((raw === '' ? undefined : Number(raw)) as never);
                    }}
                    inputProps={{
                      min: def.min,
                      max: def.max,
                      step: def.step,
                    }}
                    label={t(def.labelKey)}
                    helperText={def.hintKey ? t(def.hintKey) : undefined}
                  />
                );
              }}
            </form.Field>
          </Grid>
        );
      })}
    </Grid>
  );
}
