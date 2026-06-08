export type CameraTuningFieldKind = 'number' | 'boolean';

export type CameraTuningFieldDef = {
  key: string;
  kind: CameraTuningFieldKind;
  min?: number;
  max?: number;
  step?: number;
  labelKey: string;
  hintKey?: string;
};

/** Per-camera processor overrides + role presets (Settings + Tuning workbench). */
export const CAMERA_TUNING_FIELD_DEFS: CameraTuningFieldDef[] = [
  {
    key: 'min_confidence_binary',
    kind: 'number',
    min: 0.03,
    max: 0.6,
    step: 0.01,
    labelKey: 'settings.cameraTuningMinConfidenceBinary',
  },
  {
    key: 'min_confidence_binary_bird',
    kind: 'number',
    min: 0.03,
    max: 0.6,
    step: 0.01,
    labelKey: 'settings.cameraTuningMinConfidenceBinaryBird',
  },
  {
    key: 'min_confidence_to_process',
    kind: 'number',
    min: 0.03,
    max: 0.6,
    step: 0.01,
    labelKey: 'settings.cameraTuningMinConfidenceToProcess',
  },
  {
    key: 'min_track_duration',
    kind: 'number',
    min: 0.2,
    max: 6,
    step: 0.05,
    labelKey: 'settings.cameraTuningMinTrackDuration',
  },
  {
    key: 'min_box_size_px',
    kind: 'number',
    min: 8,
    max: 160,
    step: 1,
    labelKey: 'settings.cameraTuningMinBoxSizePx',
  },
  {
    key: 'max_box_area_norm',
    kind: 'number',
    min: 0.1,
    max: 1,
    step: 0.01,
    labelKey: 'settings.cameraTuningMaxBoxAreaNorm',
    hintKey: 'settings.cameraTuningMaxBoxAreaNormHint',
  },
  {
    key: 'scoring_giant_box_area_frac',
    kind: 'number',
    min: 0.2,
    max: 1,
    step: 0.01,
    labelKey: 'settings.cameraTuningScoringGiantBoxAreaFrac',
    hintKey: 'settings.cameraTuningScoringGiantBoxAreaFracHint',
  },
  {
    key: 'detect_record_time_offset_sec',
    kind: 'number',
    min: -2,
    max: 2,
    step: 0.05,
    labelKey: 'settings.cameraTuningDetectRecordTimeOffsetSec',
    hintKey: 'settings.cameraTuningDetectRecordTimeOffsetSecHint',
  },
  {
    key: 'openvino_binary_track_ultralytics_conf',
    kind: 'number',
    min: 0.03,
    max: 0.6,
    step: 0.01,
    labelKey: 'settings.cameraTuningOpenvinoTrackConf',
  },
  {
    key: 'track_static_reject_enabled',
    kind: 'boolean',
    labelKey: 'settings.cameraTuningTrackStaticRejectEnabled',
  },
  {
    key: 'track_static_reject_min_duration_sec',
    kind: 'number',
    min: 0.5,
    max: 10,
    step: 0.1,
    labelKey: 'settings.cameraTuningTrackStaticRejectMinDurationSec',
  },
  {
    key: 'track_static_reject_min_frames',
    kind: 'number',
    min: 1,
    max: 30,
    step: 1,
    labelKey: 'settings.cameraTuningTrackStaticRejectMinFrames',
  },
  {
    key: 'light_gate_enabled',
    kind: 'boolean',
    labelKey: 'settings.cameraTuningLightGateEnabled',
  },
  {
    key: 'binary_imgsz',
    kind: 'number',
    min: 320,
    max: 1280,
    step: 32,
    labelKey: 'settings.cameraTuningBinaryImgsz',
  },
];

export const CAMERA_TUNING_ROLES = ['feeder_close', 'feeder_far', 'custom'] as const;
export type CameraTuningRole = (typeof CAMERA_TUNING_ROLES)[number];
