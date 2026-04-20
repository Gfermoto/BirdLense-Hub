import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

type CameraRow = { stream_name?: string; name?: string };

export function CamerasListField({
  value,
  onChange,
}: {
  value:
    | Array<{ id?: string; stream_name?: string; name?: string }>
    | undefined;
  onChange: (
    v: Array<{ id?: string; stream_name?: string; name?: string }>,
  ) => void;
}) {
  const rows: CameraRow[] =
    Array.isArray(value) && value.length > 0
      ? value.map((c) => ({
          stream_name: c.stream_name ?? c.id ?? '',
          name: c.name ?? c.id ?? c.stream_name ?? '',
        }))
      : [{ stream_name: '', name: '' }];

  const sync = (newRows: CameraRow[]) => {
    const arr = newRows.map((r) => ({
      id: (r.stream_name ?? '').trim() || undefined,
      stream_name: (r.stream_name ?? '').trim(),
      name: (r.name ?? '').trim() || (r.stream_name ?? '').trim(),
    }));
    onChange(arr);
  };

  const updateRow = (i: number, field: keyof CameraRow, val: string) => {
    const next = [...rows];
    if (!next[i]) next[i] = { stream_name: '', name: '' };
    next[i] = { ...next[i], [field]: val };
    sync(next);
  };

  const addRow = () => {
    sync([...rows, { stream_name: '', name: '' }]);
  };

  const removeRow = (i: number) => {
    const next = rows.filter((_, idx) => idx !== i);
    sync(next.length ? next : [{ stream_name: '', name: '' }]);
  };

  const { t } = useTranslation();
  return (
    <Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
        {t('settings.streamNameHint')}
      </Typography>
      {rows.map((row, i) => (
        <Grid container key={i} spacing={1} sx={{ mb: 1 }} alignItems="center">
          <Grid size={{ xs: 12, sm: 6 }}>
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
          <Grid size={{ xs: 12, sm: 1 }}>
            <Button
              size="small"
              color="error"
              onClick={() => removeRow(i)}
              disabled={rows.length <= 1}
            >
              −
            </Button>
          </Grid>
        </Grid>
      ))}
      <Button size="small" onClick={addRow} sx={{ mt: 0.5 }}>
        {t('settings.addCamera')}
      </Button>
    </Box>
  );
}
