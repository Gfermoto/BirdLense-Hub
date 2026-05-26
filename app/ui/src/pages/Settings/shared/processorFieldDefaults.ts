/**
 * UI fallbacks aligned with `app/app_config/default_config.yaml` (not magic 640).
 * GET /settings returns merged config; these apply when a leaf is unset in the form.
 */

export const INFERENCE_LORES_WH_DEFAULT: [number, number] = [704, 576];
export const TRACK_REGEN_LORES_WH_DEFAULT: [number, number] = [704, 576];

export const PROCESSOR_DEFAULTS = {
  binary_imgsz: 704,
  inference_lores_px: 704,
  track_regen_lores_px: 704,
  frame_processing_warn_ms: 450,
  max_classifications_per_frame: 3,
  max_blur_checks: 3,
  blur_threshold: 100,
  min_center_dist: 0.035,
  track_regen_frame_step: 6,
  detection_quality_assumed_fps: 15,
  openvino_binary_track_ultralytics_conf: 0.3,
  openvino_binary_bird_score_scale: 1.0,
  openvino_min_confidence_binary_bird: 0.25,
  background_subtraction_history: 400,
  background_subtraction_var_threshold: 16,
  background_subtraction_min_fg_ratio: 0.07,
  background_subtraction_warmup_frames: 45,
} as const;

export type ProcessorDefaultKey = keyof typeof PROCESSOR_DEFAULTS;

export function processorDefault(key: ProcessorDefaultKey): number {
  return PROCESSOR_DEFAULTS[key];
}

export function processorNumberValue(
  value: number | null | undefined,
  key: ProcessorDefaultKey,
): number {
  if (value != null && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return processorDefault(key);
}

export function parseProcessorNumberInput(
  raw: string,
  key: ProcessorDefaultKey,
): number {
  const n = Number(raw);
  if (!Number.isFinite(n)) {
    return processorDefault(key);
  }
  return n;
}

export function whPairOrDefault(
  value: unknown,
  fallback: [number, number],
): [number, number] {
  if (Array.isArray(value) && value.length >= 2) {
    const w = Number(value[0]);
    const h = Number(value[1]);
    if (Number.isFinite(w) && Number.isFinite(h) && w > 0 && h > 0) {
      return [w, h];
    }
  }
  return fallback;
}
