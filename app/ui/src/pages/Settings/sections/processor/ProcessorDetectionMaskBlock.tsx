import { useEffect, useState } from 'react';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import FormControlLabel from '@mui/material/FormControlLabel';
import Switch from '@mui/material/Switch';
import Alert from '@mui/material/Alert';
import type { Settings } from '../../../../types';

type JsonPolygonFieldProps = {
  label: string;
  helperText: string;
  value: unknown;
  disabled?: boolean;
  onCommit: (parsed: number[][][]) => void;
};

function JsonPolygonField({
  label,
  helperText,
  value,
  disabled,
  onCommit,
}: JsonPolygonFieldProps) {
  const [draft, setDraft] = useState<string>(
    JSON.stringify(value ?? [], null, 2),
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDraft(JSON.stringify(value ?? [], null, 2));
  }, [value]);

  return (
    <TextField
      fullWidth
      multiline
      minRows={5}
      value={draft}
      onChange={(e) => {
        setDraft(e.target.value);
        setError(null);
      }}
      onBlur={() => {
        const raw = draft.trim();
        if (!raw) {
          onCommit([]);
          setError(null);
          return;
        }
        try {
          const parsed = JSON.parse(raw);
          if (!Array.isArray(parsed)) {
            setError('Must be JSON array of polygons.');
            return;
          }
          onCommit(parsed as number[][][]);
          setError(null);
        } catch {
          setError('Invalid JSON.');
        }
      }}
      label={label}
      helperText={error ?? helperText}
      error={!!error}
      disabled={disabled}
    />
  );
}

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorDetectionMaskBlock({ form }: Props) {
  return (
    <Grid container spacing={2}>
      <Grid size={{ xs: 12 }}>
        <Alert severity="info" variant="outlined">
          Detection mask editor: polygons in normalized coordinates (0..1), format{' '}
          <code>[[[x,y],[x,y],[x,y]], ...]</code>.
        </Alert>
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        <form.Field name="processor.detection_ignore_masks">
          {(field) => (
            <JsonPolygonField
              label="Ignore masks (drop detections inside)"
              helperText="Array of polygons. Box center inside polygon => reject."
              value={field.state.value}
              onCommit={(parsed) => field.handleChange(parsed)}
            />
          )}
        </form.Field>
      </Grid>
      <Grid size={{ xs: 12, md: 6 }}>
        <form.Field name="processor.detection_interest_zones">
          {(field) => (
            <JsonPolygonField
              label="Interest zones"
              helperText="Array of polygons. Use with required toggle below."
              value={field.state.value}
              onCommit={(parsed) => field.handleChange(parsed)}
            />
          )}
        </form.Field>
      </Grid>
      <Grid size={{ xs: 12 }}>
        <form.Field name="processor.detection_interest_zones_required">
          {(field) => (
            <FormControlLabel
              control={
                <Switch
                  checked={field.state.value ?? false}
                  onChange={(e) => field.handleChange(e.target.checked)}
                />
              }
              label="Require interest zones (reject detections outside zones)"
            />
          )}
        </form.Field>
      </Grid>
    </Grid>
  );
}
