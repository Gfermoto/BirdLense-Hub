import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Box from '@mui/material/Box';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import Checkbox from '@mui/material/Checkbox';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import Accordion from '@mui/material/Accordion';
import AccordionSummary from '@mui/material/AccordionSummary';
import AccordionDetails from '@mui/material/AccordionDetails';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { ServiceBlock } from '../shared/ServiceBlock';
import type { Settings } from '../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorSection({ form }: Props) {
  const { t } = useTranslation();

  return (
    <Accordion>
      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
        {t('settings.accordionProcessor')}
      </AccordionSummary>
      <AccordionDetails>
        <Box component="fieldset" sx={{ border: 'none', p: 0, m: 0, minWidth: 0 }}>
          <Box component="legend" sx={{ clip: 'rect(0,0,0,0)', position: 'absolute', width: 1, height: 1, overflow: 'hidden' }}>
            {t('settings.accordionProcessor')}
          </Box>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {t('settings.accordionProcessorDesc')}
          </Typography>

          <ServiceBlock title={t('settings.confidenceThresholdsTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.confidenceThresholdsDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <form.Field name="processor.min_confidence_binary">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0.05, max: 0.9, step: 0.05 }}
                      value={field.state.value ?? 0.22}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.confidenceDetector')}
                      helperText={t('settings.confidenceDetectorHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <form.Field name="processor.min_confidence_to_process">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 1, step: 0.05 }}
                      value={field.state.value ?? 0.30}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.confidenceClassifier')}
                      helperText={t('settings.confidenceClassifierHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <form.Field name="processor.min_confidence_to_notify">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 1, step: 0.05 }}
                      value={field.state.value ?? 0.44}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.confidenceTelegram')}
                      helperText={t('settings.confidenceTelegramHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                <form.Field name="processor.dataset_min_confidence">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 1, step: 0.05 }}
                      value={field.state.value ?? 0.50}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.confidenceDataset')}
                      helperText={t('settings.confidenceDatasetHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>
                  {t('settings.yoloSplitThresholdsTitle')}
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {t('settings.yoloSplitThresholdsDesc')}
                </Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <form.Field name="processor.min_confidence_binary_bird">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0.05, max: 0.95, step: 0.01 }}
                      value={
                        field.state.value === undefined || field.state.value === null
                          ? ''
                          : field.state.value
                      }
                      onChange={(e) => {
                        const raw = e.target.value.trim();
                        if (raw === '') {
                          field.handleChange(null);
                          return;
                        }
                        const n = Number(raw);
                        if (Number.isFinite(n)) {
                          field.handleChange(n);
                        }
                      }}
                      label={t('settings.confidenceBinaryBird')}
                      helperText={t('settings.confidenceBinaryBirdHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <form.Field name="processor.min_confidence_binary_squirrel">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0.05, max: 0.95, step: 0.01 }}
                      value={
                        field.state.value === undefined || field.state.value === null
                          ? ''
                          : field.state.value
                      }
                      onChange={(e) => {
                        const raw = e.target.value.trim();
                        if (raw === '') {
                          field.handleChange(null);
                          return;
                        }
                        const n = Number(raw);
                        if (Number.isFinite(n)) {
                          field.handleChange(n);
                        }
                      }}
                      label={t('settings.confidenceBinarySquirrel')}
                      helperText={t('settings.confidenceBinarySquirrelHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <form.Field name="processor.bird_skip_classifier_max_area_frac">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 0.5, step: 0.001 }}
                      value={
                        field.state.value === undefined || field.state.value === null
                          ? ''
                          : field.state.value
                      }
                      onChange={(e) => {
                        const raw = e.target.value.trim();
                        if (raw === '') {
                          field.handleChange(null);
                          return;
                        }
                        const n = Number(raw);
                        if (Number.isFinite(n)) {
                          field.handleChange(n);
                        }
                      }}
                      label={t('settings.birdSkipClassifierArea')}
                      helperText={t('settings.birdSkipClassifierAreaHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceProcessor')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.max_record_seconds">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      value={field.state.value ?? 60}
                      onChange={(e) => field.handleChange(Number(e.target.value))}
                      label={t('settings.maxRecordSeconds')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.max_inactive_seconds">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      value={field.state.value ?? 10}
                      onChange={(e) => field.handleChange(Number(e.target.value))}
                      label={t('settings.inactiveSeconds')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.min_track_duration">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      value={field.state.value ?? 1}
                      onChange={(e) => field.handleChange(Number(e.target.value))}
                      label={t('settings.minTrackDuration')}
                      helperText={t('settings.minTrackDurationHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.min_box_size_px">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 16, max: 256, step: 1 }}
                      value={field.state.value ?? 64}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.minBoxSizePx')}
                      helperText={t('settings.minBoxSizePxHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.post_record_seconds">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 120, step: 1 }}
                      value={field.state.value ?? 0}
                      onChange={(e) =>
                        field.handleChange(Math.max(0, Math.min(120, Number(e.target.value) || 0)))
                      }
                      label={t('settings.postRecordSeconds')}
                      helperText={t('settings.postRecordSecondsHint')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.processorMultiCameraBirdnetTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.processorMultiCameraBirdnetDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.multi_camera_groups">
                  {(field) => {
                    const val = field.state.value;
                    const str = Array.isArray(val)
                      ? (val as string[][])
                          .map((g) =>
                            Array.isArray(g)
                              ? g.map((s) => String(s).trim()).filter(Boolean).join(', ')
                              : '',
                          )
                          .filter(Boolean)
                          .join('\n')
                      : '';
                    return (
                      <TextField
                        fullWidth
                        multiline
                        minRows={3}
                        value={str}
                        onChange={(e) => {
                          const lines = e.target.value.split('\n');
                          const groups: string[][] = [];
                          for (const line of lines) {
                            const ids = line
                              .split(',')
                              .map((s) => s.trim())
                              .filter(Boolean);
                            if (ids.length) groups.push(ids);
                          }
                          field.handleChange(groups.length ? groups : []);
                        }}
                        label={t('settings.multiCameraGroups')}
                        placeholder="BirdBox, Forest"
                        helperText={t('settings.multiCameraGroupsHint')}
                      />
                    );
                  }}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.multi_camera_confidence_boost">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                      value={field.state.value ?? 0.05}
                      onChange={(e) => field.handleChange(Number(e.target.value) || 0.05)}
                      label={t('settings.multiCameraConfidenceBoost')}
                      helperText={t('settings.multiCameraConfidenceBoostHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.birdnet_mqtt_auto_confidence">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.birdnetMqttAutoConfidence')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.birdnetMqttAutoConfidenceHint')}
                </FormHelperText>
              </Grid>
              <form.Subscribe selector={(state) => state.values.processor?.birdnet_mqtt_auto_confidence}>
                {(birdnetBias) =>
                  birdnetBias ? (
                    <>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="processor.birdnet_mqtt_bias_delta">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                              value={field.state.value ?? 0.05}
                              onChange={(e) => field.handleChange(Number(e.target.value) || 0.05)}
                              label={t('settings.birdnetMqttBiasDelta')}
                              helperText={t('settings.birdnetMqttBiasDeltaHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="processor.birdnet_mqtt_bias_floor">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0.01, max: 1, step: 0.01 }}
                              value={field.state.value ?? 0.05}
                              onChange={(e) => field.handleChange(Number(e.target.value) || 0.05)}
                              label={t('settings.birdnetMqttBiasFloor')}
                              helperText={t('settings.birdnetMqttBiasFloorHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                    </>
                  ) : null
                }
              </form.Subscribe>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.confidenceAdvanced')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.species_confidence_overrides">
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
                          const lines = e.target.value.split('\n').filter(Boolean);
                          const obj: Record<string, number> = {};
                          for (const line of lines) {
                            const idx = line.indexOf(':');
                            if (idx > 0) {
                              const k = line.slice(0, idx).trim();
                              const v = parseFloat(line.slice(idx + 1).trim());
                              if (!isNaN(v) && v >= 0 && v <= 1) obj[k] = v;
                            }
                          }
                          field.handleChange(Object.keys(obj).length ? obj : {});
                        }}
                        label={t('settings.speciesConfidenceOverrides')}
                        placeholder="Pileated Woodpecker: 0.05"
                        helperText={t('settings.speciesConfidenceOverridesHint')}
                      />
                    );
                  }}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                  {t('settings.ebirdRegionalTopConfidenceIntro')}
                </Typography>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.ebird_regional_top_auto_confidence">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value ?? true}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.ebirdRegionalTopAutoConfidence')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.ebirdRegionalTopAutoConfidenceHint')}
                </FormHelperText>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.ebird_regional_top_confidence_delta">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 0.5, step: 0.01 }}
                      value={field.state.value ?? 0.05}
                      onChange={(e) => field.handleChange(Number(e.target.value) || 0.05)}
                      label={t('settings.ebirdRegionalTopConfidenceDelta')}
                      helperText={t('settings.ebirdRegionalTopConfidenceDeltaHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.ebird_regional_top_confidence_floor">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0.01, max: 1, step: 0.01 }}
                      value={field.state.value ?? 0.05}
                      onChange={(e) => field.handleChange(Number(e.target.value) || 0.05)}
                      label={t('settings.ebirdRegionalTopConfidenceFloor')}
                      helperText={t('settings.ebirdRegionalTopConfidenceFloorHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="ui.unknown_confidence_threshold">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 1, step: 0.05 }}
                      value={field.state.value ?? 0.5}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.unknownConfidenceThreshold')}
                      helperText={t('settings.unknownConfidenceThresholdHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.falsePositiveGuardrailsTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.falsePositiveGuardrailsDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 8 }}>
                <form.Field name="processor.detector_scope">
                  {(field) => {
                    const val = Array.isArray(field.state.value) ? field.state.value : [];
                    const str = val.map((item) => String(item).trim()).filter(Boolean).join(', ');
                    return (
                      <TextField
                        fullWidth
                        multiline
                        minRows={2}
                        value={str}
                        onChange={(e) => {
                          const items = e.target.value
                            .split(/[\n,]/)
                            .map((s) => s.trim())
                            .filter(Boolean);
                          field.handleChange(items.length ? items : []);
                        }}
                        label={t('settings.detectorScope')}
                        helperText={t('settings.detectorScopeHint')}
                        placeholder="Bird, Squirrel"
                      />
                    );
                  }}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 4 }}>
                <form.Field name="processor.classifier_fallback_bird">
                  {(field) => (
                    <FormControl fullWidth>
                      <FormControlLabel
                        control={
                          <Switch
                            checked={field.state.value !== false}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.classifierFallbackBird')}
                      />
                      <FormHelperText>{t('settings.classifierFallbackBirdHint')}</FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.included_bird_families">
                  {(field) => {
                    const val = Array.isArray(field.state.value) ? field.state.value : [];
                    const str = val.map((item) => String(item).trim()).filter(Boolean).join('\n');
                    return (
                      <TextField
                        fullWidth
                        multiline
                        minRows={3}
                        value={str}
                        onChange={(e) => {
                          const items = e.target.value
                            .split(/[\n,]/)
                            .map((s) => s.trim())
                            .filter(Boolean);
                          field.handleChange(items.length ? items : []);
                        }}
                        label={t('settings.birdFamilies')}
                        helperText={t('settings.includedBirdFamiliesHint')}
                        placeholder="Perching Birds"
                      />
                    );
                  }}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.lightGateTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.lightGateDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.light_gate_enabled">
                  {(field) => (
                    <FormControl fullWidth>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={field.state.value !== false}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.lightGateEnabled')}
                      />
                      <FormHelperText>{t('settings.lightGateEnabledHelp')}</FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.light_gate_min_brightness">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 255, step: 1 }}
                      value={field.state.value ?? 25}
                      onChange={(e) =>
                        field.handleChange(Number(e.target.value) || undefined)
                      }
                      label={t('settings.lightGateMinBrightness')}
                      helperText={t('settings.lightGateMinBrightnessHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.light_gate_min_contrast">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 255, step: 1 }}
                      value={field.state.value ?? 20}
                      onChange={(e) =>
                        field.handleChange(Number(e.target.value) || undefined)
                      }
                      label={t('settings.lightGateMinContrast')}
                      helperText={t('settings.lightGateMinContrastHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.serviceProcessor')}>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.spectrogram_px_per_sec">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      value={field.state.value ?? 200}
                      onChange={(e) => field.handleChange(Number(e.target.value))}
                      label={t('settings.spectrogramDetail')}
                      helperText={t('settings.spectrogramDetailHelp')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="processor.generate_spectrogram_always">
                  {(field) => (
                    <FormControl fullWidth>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={field.state.value !== false}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.generateSpectrogramAlways')}
                      />
                      <FormHelperText>{t('settings.generateSpectrogramAlwaysHelp')}</FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.tracker">
                  {(field) => (
                    <TextField
                      fullWidth
                      value={field.state.value ?? ''}
                      onChange={(e) => field.handleChange(e.target.value)}
                      label={t('settings.objectTracker')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="processor.save_dataset_crops">
                  {(field) => (
                    <FormControl fullWidth>
                      <FormControlLabel
                        control={
                          <Checkbox
                            checked={!!field.state.value}
                            onChange={(e) => field.handleChange(e.target.checked)}
                          />
                        }
                        label={t('settings.saveDatasetCrops')}
                      />
                      <FormHelperText>{t('settings.saveDatasetCropsHelp')}</FormHelperText>
                    </FormControl>
                  )}
                </form.Field>
              </Grid>
            </Grid>
          </ServiceBlock>

          <ServiceBlock title={t('settings.frigateFusionTitle')}>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
              {t('settings.frigateFusionDesc')}
            </Typography>
            <Grid container spacing={2}>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <form.Field name="detection.min_confidence_to_store">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0.05, max: 1, step: 0.02 }}
                      value={field.state.value ?? 0.36}
                      onChange={(e) => field.handleChange(Number(e.target.value) || undefined)}
                      label={t('settings.detectionMinConfidenceToStore')}
                      helperText={t('settings.detectionMinConfidenceToStoreHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <form.Field name="detection.merge_window_seconds">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 1, max: 120, step: 1 }}
                      value={field.state.value ?? 6}
                      onChange={(e) => field.handleChange(Number(e.target.value) || 6)}
                      label={t('settings.detectionMergeWindow')}
                      helperText={t('settings.detectionMergeWindowHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                <form.Field name="detection.dedup_window_seconds">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 5, max: 600, step: 1 }}
                      value={field.state.value ?? 60}
                      onChange={(e) => field.handleChange(Number(e.target.value) || 60)}
                      label={t('settings.detectionDedupWindow')}
                      helperText={t('settings.detectionDedupWindowHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="detection.one_per_species">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value !== false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.detectionOnePerSpecies')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.detectionOnePerSpeciesHint')}
                </FormHelperText>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="detection.cross_source_confidence_bonus">
                  {(field) => (
                    <TextField
                      fullWidth
                      type="number"
                      inputProps={{ min: 0, max: 0.3, step: 0.01 }}
                      value={field.state.value ?? 0.02}
                      onChange={(e) => field.handleChange(Number(e.target.value) || 0)}
                      label={t('settings.detectionCrossSourceBonus')}
                      helperText={t('settings.detectionCrossSourceBonusHint')}
                    />
                  )}
                </form.Field>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <Typography variant="subtitle2" sx={{ mt: 1, mb: 1 }}>
                  {t('settings.frigateStandaloneHeading')}
                </Typography>
              </Grid>
              <Grid size={{ xs: 12 }}>
                <form.Field name="detection.frigate_standalone_when_no_yolo">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value !== false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.frigateStandaloneWhenNoYolo')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.frigateStandaloneWhenNoYoloHint')}
                </FormHelperText>
              </Grid>
              <form.Subscribe
                selector={(state) => state.values.detection?.frigate_standalone_when_no_yolo}
              >
                {(standaloneOn) =>
                  standaloneOn !== false ? (
                    <>
                      <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                        <form.Field name="detection.frigate_standalone_min_score">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 1, step: 0.05 }}
                              value={field.state.value ?? 0.4}
                              onChange={(e) =>
                                field.handleChange(Number(e.target.value) || undefined)
                              }
                              label={t('settings.frigateStandaloneMinScore')}
                              helperText={t('settings.frigateStandaloneMinScoreHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                        <form.Field name="detection.frigate_standalone_missing_score_fallback">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 1, step: 0.05 }}
                              value={
                                field.state.value === undefined ||
                                field.state.value === null
                                  ? 0.68
                                  : field.state.value
                              }
                              onChange={(e) => {
                                const raw = e.target.value;
                                if (raw === '') {
                                  field.handleChange(undefined);
                                  return;
                                }
                                const n = Number(raw);
                                field.handleChange(Number.isNaN(n) ? undefined : n);
                              }}
                              label={t('settings.frigateStandaloneMissingFallback')}
                              helperText={t('settings.frigateStandaloneMissingFallbackHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                        <form.Field name="detection.frigate_standalone_notify">
                          {(field) => (
                            <FormControl fullWidth>
                              <FormControlLabel
                                control={
                                  <Switch
                                    checked={field.state.value !== false}
                                    onChange={(e) => field.handleChange(e.target.checked)}
                                  />
                                }
                                label={t('settings.frigateStandaloneNotify')}
                              />
                              <FormHelperText>
                                {t('settings.frigateStandaloneNotifyHint')}
                              </FormHelperText>
                            </FormControl>
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12 }}>
                        <Typography variant="subtitle2" sx={{ mt: 1, mb: 0.5 }}>
                          {t('settings.frigateStandaloneExcludedHeading')}
                        </Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                          {t('settings.frigateStandaloneExcludedIntro')}
                        </Typography>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="detection.frigate_standalone_excluded_min_score">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 1, step: 0.05 }}
                              value={field.state.value ?? 0}
                              onChange={(e) =>
                                field.handleChange(Number(e.target.value) || 0)
                              }
                              label={t('settings.frigateStandaloneExcludedMinScore')}
                              helperText={t('settings.frigateStandaloneExcludedMinScoreHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="detection.frigate_standalone_excluded_missing_score_fallback">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 1, step: 0.05 }}
                              value={
                                field.state.value === undefined ||
                                field.state.value === null
                                  ? 0.58
                                  : field.state.value
                              }
                              onChange={(e) => {
                                const raw = e.target.value;
                                if (raw === '') {
                                  field.handleChange(undefined);
                                  return;
                                }
                                const n = Number(raw);
                                field.handleChange(Number.isNaN(n) ? undefined : n);
                              }}
                              label={t('settings.frigateStandaloneExcludedMissingFallback')}
                              helperText={t(
                                'settings.frigateStandaloneExcludedMissingFallbackHint',
                              )}
                            />
                          )}
                        </form.Field>
                      </Grid>
                    </>
                  ) : null
                }
              </form.Subscribe>
              <Grid size={{ xs: 12 }}>
                <Typography variant="subtitle2" sx={{ mt: 2, mb: 1 }}>
                  {t('settings.absorbGenericBirdHeading')}
                </Typography>
              </Grid>
              <Grid size={{ xs: 12, sm: 6 }}>
                <form.Field name="detection.absorb_generic_bird">
                  {(field) => (
                    <FormControlLabel
                      control={
                        <Switch
                          checked={field.state.value !== false}
                          onChange={(e) => field.handleChange(e.target.checked)}
                        />
                      }
                      label={t('settings.absorbGenericBird')}
                    />
                  )}
                </form.Field>
                <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
                  {t('settings.absorbGenericBirdHint')}
                </FormHelperText>
              </Grid>
              <form.Subscribe selector={(state) => state.values.detection?.absorb_generic_bird}>
                {(absorb) =>
                  absorb !== false ? (
                    <>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="detection.absorb_generic_bird_overlap_min_sec">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 10, step: 0.05 }}
                              value={field.state.value ?? 0.1}
                              onChange={(e) =>
                                field.handleChange(Number(e.target.value) || 0.1)
                              }
                              label={t('settings.absorbGenericBirdOverlap')}
                              helperText={t('settings.absorbGenericBirdOverlapHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                      <Grid size={{ xs: 12, sm: 6 }}>
                        <form.Field name="detection.absorb_generic_bird_min_classifier_confidence">
                          {(field) => (
                            <TextField
                              fullWidth
                              type="number"
                              inputProps={{ min: 0, max: 1, step: 0.02 }}
                              value={field.state.value ?? 0.24}
                              onChange={(e) =>
                                field.handleChange(Number(e.target.value) || undefined)
                              }
                              label={t('settings.absorbGenericBirdMinClassifier')}
                              helperText={t('settings.absorbGenericBirdMinClassifierHint')}
                            />
                          )}
                        </form.Field>
                      </Grid>
                    </>
                  ) : null
                }
              </form.Subscribe>
            </Grid>
          </ServiceBlock>

        </Box>
      </AccordionDetails>
    </Accordion>
  );
}
