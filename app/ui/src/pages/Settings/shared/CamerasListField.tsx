import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

type CameraRowUi = {
  stream_name?: string;
  detect_stream_name?: string;
  name?: string;
};

export function CamerasListField({
  value,
  onChange,
}: {
  value:
    | Array<{
        id?: string;
        stream_name?: string;
        detect_stream_name?: string;
        name?: string;
      }>
    | undefined;
  onChange: (
    v: Array<{
      id?: string;
      stream_name?: string;
      detect_stream_name?: string;
      name?: string;
    }>,
  ) => void;
}) {
  const rows: CameraRowUi[] =
    Array.isArray(value) && value.length > 0
      ? value.map((c) => ({
          stream_name: c.stream_name ?? c.id ?? '',
          detect_stream_name: c.detect_stream_name ?? '',
          name: c.name ?? c.id ?? c.stream_name ?? '',
        }))
      : [{ stream_name: '', detect_stream_name: '', name: '' }];

  const sync = (newRows: CameraRowUi[]) => {
    const arr = newRows.map((r) => {
      const stream_name = (r.stream_name ?? '').trim();
      const name = (r.name ?? '').trim() || stream_name;
      const id = stream_name || undefined;
      const row: {
        id?: string;
        stream_name: string;
        name: string;
        detect_stream_name?: string;
      } = {
        id,
        stream_name,
        name,
      };
      const ds = (r.detect_stream_name ?? '').trim();
      if (ds) {
        row.detect_stream_name = ds;
      }
      return row;
    });
    onChange(arr);
  };

  const updateRow = (i: number, field: keyof CameraRowUi, val: string) => {
    const next = [...rows];
    if (!next[i]) {
      next[i] = { stream_name: '', detect_stream_name: '', name: '' };
    }
    next[i] = { ...next[i], [field]: val };
    sync(next);
  };

  const addRow = () => {
    sync([...rows, { stream_name: '', detect_stream_name: '', name: '' }]);
  };

  const removeRow = (i: number) => {
    const next = rows.filter((_, idx) => idx !== i);
    sync(
      next.length
        ? next
        : [{ stream_name: '', detect_stream_name: '', name: '' }],
    );
  };

  const { t } = useTranslation();
  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('settings.streamNameHint')}
      </Typography>
      {rows.map((row, i) => (
        <Grid
          container
          key={i}
          spacing={1}
          sx={{ mb: 2 }}
          alignItems="flex-start"
        >
          <Grid size={{ xs: 12, sm: 5 }}>
            <TextField
              fullWidth
              size="small"
              value={row.stream_name ?? ''}
              onChange={(e) => updateRow(i, 'stream_name', e.target.value)}
              label={t('settings.streamName')}
              placeholder="BirdBox"
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 5 }}>
            <TextField
              fullWidth
              size="small"
              value={row.name ?? ''}
              onChange={(e) => updateRow(i, 'name', e.target.value)}
              label={t('settings.cameraName')}
              placeholder={t('settings.cameraPlaceholder')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 2 }} sx={{ pt: { sm: 0.5 } }}>
            <Button
              size="small"
              color="error"
              onClick={() => removeRow(i)}
              disabled={rows.length <= 1}
            >
              −
            </Button>
          </Grid>
          <Grid size={{ xs: 12 }}>
            <TextField
              fullWidth
              size="small"
              value={row.detect_stream_name ?? ''}
              onChange={(e) =>
                updateRow(i, 'detect_stream_name', e.target.value)
              }
              label={t('settings.detectStreamName')}
              placeholder={t('settings.detectStreamNamePlaceholder')}
              helperText={t('settings.detectStreamNameHint')}
            />
          </Grid>
        </Grid>
      ))}
      <Button size="small" onClick={addRow} sx={{ mt: 0.5 }}>
        {t('settings.addCamera')}
      </Button>
    </Box>
  );
}
