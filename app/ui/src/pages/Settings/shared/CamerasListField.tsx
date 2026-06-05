import { useTranslation } from 'react-i18next';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Grid from '@mui/material/Grid2';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';

type CameraRowUi = {
  id?: string;
  camera_slot?: string;
  stream_name?: string;
  detect_stream_name?: string;
  name?: string;
};

function defaultSlot(index: number): string {
  return `camera_${index + 1}`;
}

export function CamerasListField({
  value,
  onChange,
}: {
  value:
    | Array<{
        id?: string;
        camera_slot?: string;
        stream_name?: string;
        detect_stream_name?: string;
        name?: string;
      }>
    | undefined;
  onChange: (
    v: Array<{
      id?: string;
      camera_slot?: string;
      stream_name?: string;
      detect_stream_name?: string;
      name?: string;
    }>,
  ) => void;
}) {
  const rows: CameraRowUi[] =
    Array.isArray(value) && value.length > 0
      ? value.map((c, idx) => ({
          id: c.stream_name ?? c.id ?? '',
          camera_slot: (c.camera_slot ?? '').trim() || defaultSlot(idx),
          stream_name: c.stream_name ?? c.id ?? '',
          detect_stream_name: c.detect_stream_name ?? '',
          name: c.name ?? c.id ?? c.stream_name ?? '',
        }))
      : [{ id: '', camera_slot: defaultSlot(0), stream_name: '', detect_stream_name: '', name: '' }];

  const sync = (newRows: CameraRowUi[]) => {
    const arr = newRows.map((r, idx) => {
      const stream_name = (r.stream_name ?? '').trim();
      const name = (r.name ?? '').trim() || stream_name;
      const camera_slot = (r.camera_slot ?? '').trim() || defaultSlot(idx);
      const row: {
        id: string;
        camera_slot: string;
        stream_name: string;
        name: string;
        detect_stream_name?: string;
      } = {
        id: stream_name,
        camera_slot,
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
      next[i] = {
        id: '',
        camera_slot: defaultSlot(i),
        stream_name: '',
        detect_stream_name: '',
        name: '',
      };
    }
    next[i] = { ...next[i], [field]: val };
    sync(next);
  };

  const addRow = () => {
    sync([
      ...rows,
      {
        id: '',
        camera_slot: defaultSlot(rows.length),
        stream_name: '',
        detect_stream_name: '',
        name: '',
      },
    ]);
  };

  const removeRow = (i: number) => {
    const next = rows.filter((_, idx) => idx !== i);
    sync(
      next.length
        ? next
        : [{ id: '', camera_slot: defaultSlot(0), stream_name: '', detect_stream_name: '', name: '' }],
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
              placeholder={t('settings.streamNamePlaceholder')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 6 }}>
            <TextField
              fullWidth
              size="small"
              value={row.name ?? ''}
              onChange={(e) => updateRow(i, 'name', e.target.value)}
              label={t('settings.cameraName')}
              placeholder={t('settings.cameraPlaceholder')}
            />
          </Grid>
          <Grid size={{ xs: 12, sm: 1 }} sx={{ pt: { sm: 0.5 } }}>
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
              required={Boolean((row.stream_name ?? '').trim())}
              value={row.detect_stream_name ?? ''}
              onChange={(e) =>
                updateRow(i, 'detect_stream_name', e.target.value)
              }
              label={t('settings.detectStreamName')}
              placeholder={t('settings.detectStreamNamePlaceholder')}
              error={
                Boolean((row.stream_name ?? '').trim()) &&
                (row.detect_stream_name ?? '').trim() ===
                  (row.stream_name ?? '').trim()
              }
              helperText={
                Boolean((row.stream_name ?? '').trim()) &&
                (row.detect_stream_name ?? '').trim() ===
                  (row.stream_name ?? '').trim()
                  ? t('settings.detectStreamNameSameAsRecordError')
                  : t('settings.detectStreamNameHint')
              }
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
