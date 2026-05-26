import { useCallback, useState } from 'react';
import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Alert from '@mui/material/Alert';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import FormControl from '@mui/material/FormControl';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormHelperText from '@mui/material/FormHelperText';
import Grid from '@mui/material/Grid2';
import InputLabel from '@mui/material/InputLabel';
import MenuItem from '@mui/material/MenuItem';
import Select from '@mui/material/Select';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import { fetchMotionPreview, type MotionPreviewMode } from '../../../../api/motionPreview';
import type { Settings } from '../../../../types';
import { ServiceBlock } from '../../shared/ServiceBlock';
import { ProcessorNumberField } from '../../shared/ProcessorNumberField';
import { ProcessorBackgroundSubtractionBlock } from './ProcessorBackgroundSubtractionBlock';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorMotionCalibrationBlock({ form }: Props) {
  const { t } = useTranslation();
  const [previewMode, setPreviewMode] = useState<MotionPreviewMode>('detection_mog2');
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [maskUrl, setMaskUrl] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<
    { level: string; code: string; message: string }[]
  >([]);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const runPreview = useCallback(async () => {
    setLoading(true);
    setPreviewError(null);
    try {
      const values = form.state.values;
      const overrides = {
        processor: values.processor ?? {},
        triggers: { opencv: values.triggers?.opencv ?? {} },
      };
      const body = await fetchMotionPreview({
        mode: previewMode,
        overrides,
      });
      setWarnings(body.warnings ?? []);
      if (body.image_jpeg_base64) {
        setPreviewUrl(`data:image/jpeg;base64,${body.image_jpeg_base64}`);
      }
      if (body.mask_jpeg_base64) {
        setMaskUrl(`data:image/jpeg;base64,${body.mask_jpeg_base64}`);
      }
    } catch (e) {
      setPreviewError(e instanceof Error ? e.message : String(e));
      setPreviewUrl(null);
      setMaskUrl(null);
      setWarnings([]);
    } finally {
      setLoading(false);
    }
  }, [form, previewMode]);

  return (
    <ServiceBlock title={t('settings.motionCalibrationTitle')}>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
        {t('settings.motionCalibrationDesc')}
      </Typography>

      <ProcessorBackgroundSubtractionBlock form={form} />

      <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
        {t('settings.motionCalibrationTriggerTitle')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="triggers.opencv.detection_method">
            {(field) => (
              <FormControl fullWidth>
                <InputLabel id="opencv-detection-method-label">
                  {t('settings.motionCalibrationDetectionMethod')}
                </InputLabel>
                <Select
                  labelId="opencv-detection-method-label"
                  label={t('settings.motionCalibrationDetectionMethod')}
                  value={field.state.value ?? 'frame_diff'}
                  onChange={(e) => field.handleChange(e.target.value)}
                >
                  <MenuItem value="frame_diff">frame_diff</MenuItem>
                  <MenuItem value="mog2">mog2</MenuItem>
                  <MenuItem value="hybrid">hybrid</MenuItem>
                </Select>
                <FormHelperText>
                  {t('settings.motionCalibrationDetectionMethodHint')}
                </FormHelperText>
              </FormControl>
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="triggers.opencv.mog2_var_threshold">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 4, max: 128, step: 1 }}
                value={field.state.value ?? 24}
                onChange={(e) => field.handleChange(Number(e.target.value) || 24)}
                label={t('settings.motionCalibrationMog2VarThreshold')}
                helperText={t('settings.motionCalibrationMog2VarThresholdHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="triggers.opencv.mog2_min_contour_area">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 20, max: 20000, step: 10 }}
                value={field.state.value ?? 220}
                onChange={(e) => field.handleChange(Number(e.target.value) || 220)}
                label={t('settings.motionCalibrationMog2MinArea')}
                helperText={t('settings.motionCalibrationMog2MinAreaHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="triggers.opencv.mog2_detect_shadows">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value === true}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.motionCalibrationMog2Shadows')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
        {t('settings.motionCalibrationStaticTitle')}
      </Typography>
      <Grid container spacing={2}>
        <Grid size={{ xs: 12 }}>
          <form.Field name="processor.static_object_suppression_enabled">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value === true}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.motionCalibrationStaticEnabled')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.static_scene_bird_min_confidence">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.01 }}
                value={field.state.value ?? 0.25}
                onChange={(e) => field.handleChange(Number(e.target.value) || 0.25)}
                label={t('settings.motionCalibrationStaticConfFloor')}
                helperText={t('settings.motionCalibrationStaticConfFloorHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="processor.static_temporal_max_jitter_px">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0.5, max: 32, step: 0.5 }}
                value={field.state.value ?? 2}
                onChange={(e) => field.handleChange(Number(e.target.value) || 2)}
                label={t('settings.motionCalibrationStaticJitter')}
                helperText={t('settings.motionCalibrationStaticJitterHint')}
              />
            )}
          </form.Field>
        </Grid>
      </Grid>

      <Box sx={{ mt: 2, display: 'flex', flexWrap: 'wrap', gap: 1, alignItems: 'center' }}>
        <FormControl size="small" sx={{ minWidth: 200 }}>
          <InputLabel id="motion-preview-mode">{t('settings.motionCalibrationPreviewMode')}</InputLabel>
          <Select
            labelId="motion-preview-mode"
            label={t('settings.motionCalibrationPreviewMode')}
            value={previewMode}
            onChange={(e) => setPreviewMode(e.target.value as MotionPreviewMode)}
          >
            <MenuItem value="detection_mog2">{t('settings.motionCalibrationPreviewDetection')}</MenuItem>
            <MenuItem value="trigger_mog2">{t('settings.motionCalibrationPreviewTrigger')}</MenuItem>
            <MenuItem value="static">{t('settings.motionCalibrationPreviewStatic')}</MenuItem>
          </Select>
        </FormControl>
        <Button variant="contained" onClick={() => void runPreview()} disabled={loading}>
          {loading ? t('settings.motionCalibrationPreviewLoading') : t('settings.motionCalibrationPreviewBtn')}
        </Button>
      </Box>

      {previewError ? (
        <Alert severity="error" sx={{ mt: 2 }}>
          {previewError}
        </Alert>
      ) : null}

      {warnings.map((w) => (
        <Alert key={w.code} severity={w.level === 'warning' ? 'warning' : 'info'} sx={{ mt: 1 }}>
          {w.message}
        </Alert>
      ))}

      {(previewUrl || maskUrl) && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          {previewUrl ? (
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="caption" color="text.secondary">
                {t('settings.motionCalibrationPreviewOverlay')}
              </Typography>
              <Box
                component="img"
                src={previewUrl}
                alt={t('settings.motionCalibrationPreviewOverlay')}
                sx={{ width: '100%', borderRadius: 1, border: 1, borderColor: 'divider' }}
              />
            </Grid>
          ) : null}
          {maskUrl ? (
            <Grid size={{ xs: 12, md: 6 }}>
              <Typography variant="caption" color="text.secondary">
                {t('settings.motionCalibrationPreviewMask')}
              </Typography>
              <Box
                component="img"
                src={maskUrl}
                alt={t('settings.motionCalibrationPreviewMask')}
                sx={{ width: '100%', borderRadius: 1, border: 1, borderColor: 'divider' }}
              />
            </Grid>
          ) : null}
        </Grid>
      )}
    </ServiceBlock>
  );
}
