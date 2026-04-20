import { useTranslation } from 'react-i18next';
import type { ReactFormExtendedApi } from '@tanstack/react-form';
import Grid from '@mui/material/Grid2';
import Switch from '@mui/material/Switch';
import TextField from '@mui/material/TextField';
import Typography from '@mui/material/Typography';
import FormControlLabel from '@mui/material/FormControlLabel';
import FormControl from '@mui/material/FormControl';
import FormHelperText from '@mui/material/FormHelperText';
import { ServiceBlock } from '../../shared/ServiceBlock';
import type { Settings } from '../../../../types';

type Props = {
  form: ReactFormExtendedApi<Settings, undefined>;
};

export function ProcessorFrigateFusionBlock({ form }: Props) {
  const { t } = useTranslation();

  return (
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
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || undefined)
                }
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
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 6)
                }
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
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 60)
                }
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
                onChange={(e) =>
                  field.handleChange(Number(e.target.value) || 0)
                }
                label={t('settings.detectionCrossSourceBonus')}
                helperText={t('settings.detectionCrossSourceBonusHint')}
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <Typography variant="subtitle2" sx={{ mt: 2, mb: 0.5 }}>
            {t('settings.learnedFusionHeading')}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
            {t('settings.learnedFusionIntro')}
          </Typography>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="detection.use_learned_fusion">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={Boolean(field.state.value)}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.learnedFusionEnable')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.learnedFusionEnableHint')}
          </FormHelperText>
        </Grid>
        <Grid size={{ xs: 12 }}>
          <form.Field name="detection.fusion_model_path">
            {(field) => (
              <TextField
                fullWidth
                value={field.state.value ?? ''}
                onChange={(e) => field.handleChange(e.target.value)}
                label={t('settings.learnedFusionModelPath')}
                helperText={t('settings.learnedFusionModelPathHint')}
                placeholder="models/fusion/fusion_state.pt"
              />
            )}
          </form.Field>
        </Grid>
        <Grid size={{ xs: 12, sm: 6 }}>
          <form.Field name="detection.fusion_alpha">
            {(field) => (
              <TextField
                fullWidth
                type="number"
                inputProps={{ min: 0, max: 1, step: 0.05 }}
                value={
                  field.state.value === undefined || field.state.value === null
                    ? 0.6
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
                label={t('settings.learnedFusionAlpha')}
                helperText={t('settings.learnedFusionAlphaHint')}
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
        <Grid size={{ xs: 12 }}>
          <form.Field name="detection.frigate_standalone_when_no_accepted_species">
            {(field) => (
              <FormControlLabel
                control={
                  <Switch
                    checked={field.state.value !== false}
                    onChange={(e) => field.handleChange(e.target.checked)}
                  />
                }
                label={t('settings.frigateStandaloneWhenNoAcceptedSpecies')}
              />
            )}
          </form.Field>
          <FormHelperText sx={{ ml: 0, mt: 0.5 }}>
            {t('settings.frigateStandaloneWhenNoAcceptedSpeciesHint')}
          </FormHelperText>
        </Grid>
        <form.Subscribe
          selector={(state) =>
            state.values.detection?.frigate_standalone_when_no_yolo
          }
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
                          field.handleChange(
                            Number(e.target.value) || undefined,
                          )
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
                        helperText={t(
                          'settings.frigateStandaloneMissingFallbackHint',
                        )}
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
                              onChange={(e) =>
                                field.handleChange(e.target.checked)
                              }
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
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{ mb: 1 }}
                  >
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
                        helperText={t(
                          'settings.frigateStandaloneExcludedMinScoreHint',
                        )}
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
                        label={t(
                          'settings.frigateStandaloneExcludedMissingFallback',
                        )}
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
        <form.Subscribe
          selector={(state) => state.values.detection?.absorb_generic_bird}
        >
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
                          field.handleChange(
                            Number(e.target.value) || undefined,
                          )
                        }
                        label={t('settings.absorbGenericBirdMinClassifier')}
                        helperText={t(
                          'settings.absorbGenericBirdMinClassifierHint',
                        )}
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
  );
}
