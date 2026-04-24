import axios from 'axios';
import { BASE_API_URL } from './client';

export interface SpeciesDataQualityReport {
  species_total: number;
  duplicate_name_group_count: number;
  duplicate_name_groups: Array<{
    normalized_name: string;
    count: number;
    species: Array<{ id: number; name: string }>;
  }>;
  hints: Record<string, string>;
}

export const fetchSpeciesDataQuality =
  async (): Promise<SpeciesDataQualityReport> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/species-registry/data-quality`,
      {
        params: { suspect_limit: 500, duplicate_limit: 100 },
      },
    );
    return response.data;
  };

export interface ClassifierDatasetAlignmentReport {
  classifier_weights_path: string;
  classifier_weights_resolved: string;
  classifier_readable: boolean;
  classifier_error: string | null;
  classifier_class_count: number;
  in_classifier_not_in_catalog: string[];
  in_classifier_not_in_catalog_count: number;
  in_catalog_not_in_classifier: Array<{ id: number; name: string }>;
  in_catalog_not_in_classifier_count: number;
  dataset_folder_count: number;
  dataset_folders_without_catalog_match: string[];
  dataset_folders_without_catalog_match_count: number;
  dataset_folders_species_not_in_classifier: Array<{
    folder: string;
    species_id: number;
    species_name: string;
  }>;
  dataset_folders_species_not_in_classifier_count: number;
  species_with_video_detections: number;
  catalog_species_total: number;
  catalog_classifier_dataset_aligned?: boolean;
  hints?: Record<string, string>;
}

export interface CatalogCoverageMetrics {
  observed_species_count: number;
  dataset_species_count: number;
  full_eu_species_count: number;
  observed_in_full_eu_count: number;
  dataset_in_full_eu_count: number;
  observed_vs_full_eu_percent: number;
  dataset_vs_full_eu_percent: number;
  observed_in_dataset_count: number;
  observed_in_dataset_percent: number;
  tuning_candidate_count: number;
  tuning_candidates: Array<{ id: number; name: string }>;
}

export interface CatalogCardsCoverageSnapshot {
  allowlist_total: number;
  /** Allowlist file lines that resolved to some ``Species`` row (can exceed unique species). */
  allowlist_lines_matched: number;
  /** Distinct ``Species`` rows referenced by at least one allowlist line. */
  species_matched: number;
  with_image: number;
  with_description: number;
  complete_cards: number;
  completion_percent: number;
}

export interface CatalogRepairStatus {
  status: 'idle' | 'running' | 'done' | 'error';
  result: null | {
    checked: number;
    metadata_fixed: number;
    images_replaced_from_inat: number;
    images_realigned_allowlist_science?: number;
    still_missing: number;
    /** Wikipedia/iNat enrich raised (see web logs). */
    enrich_exceptions?: number;
    dry_run: boolean;
    auto?: boolean;
    coverage_after?: CatalogCardsCoverageSnapshot;
  };
  error: string | null;
  progress: null | {
    auto?: boolean;
    limit: number;
    coverage_before?: CatalogCardsCoverageSnapshot;
  };
  coverage_now: CatalogCardsCoverageSnapshot;
  schedule?: {
    autorun_enabled: boolean;
    interval_min: number;
    limit: number;
    next_run_in_sec: number;
    /** Round-robin offset for low-limit catalog repair (see BIRDLENSE_CATALOG_REPAIR_LIMIT). */
    priority_rotate?: number;
  };
}

export const fetchClassifierDatasetAlignment =
  async (): Promise<ClassifierDatasetAlignmentReport> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/species-registry/classifier-dataset-alignment`,
      {
        params: {
          classifier_limit: 400,
          catalog_limit: 300,
          dataset_limit: 150,
        },
      },
    );
    return response.data;
  };

export const fetchCatalogCoverageMetrics =
  async (): Promise<CatalogCoverageMetrics> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/species-registry/coverage-metrics`,
    );
    return response.data;
  };

export const fetchCatalogRepairStatus =
  async (): Promise<CatalogRepairStatus> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/species-registry/repair-cards/status`,
      { withCredentials: true },
    );
    return response.data;
  };

export const startCatalogRepair = async (
  limit = 6000,
): Promise<{ message: string; status: CatalogRepairStatus }> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/species-registry/repair-cards/start`,
    { limit },
    { withCredentials: true },
  );
  return response.data;
};

export type SystemJobStatus = {
  status: string;
  result?: Record<string, unknown> | null;
  error?: string | null;
  progress?: Record<string, unknown> | null;
};

export type RecognitionImprovementSummary = {
  active_mode: 'disabled' | 'heuristic' | 'trained' | string;
  settings: {
    enabled: boolean;
    alpha: number;
  };
  feedback: {
    corrected_examples: number;
    unique_videos: number;
    unique_species: number;
    ready_for_training: boolean;
    examples_until_ready: number;
    latest_feedback_at?: string | null;
    thresholds?: {
      corrected_examples?: number;
      unique_videos?: number;
      unique_species?: number;
    };
  };
  model: {
    label: string;
    active_model_id?: string | null;
    configured_path?: string;
    trained_model_count: number;
    last_trained_at?: string | null;
    can_roll_back: boolean;
  };
};

export type BirdnetSpeciesFifoRow = {
  display_label: string;
  canonical_for_video: string;
  scientific_name?: string | null;
  active: number;
  last_heard_at?: string;
  seconds_since_heard?: number;
  event_count: number;
};

export type BirdnetFifoDialogSnapshot = {
  queue_len?: number;
  fifo_cap?: number;
  fifo_fill_ratio?: number;
  mqtt_connected?: boolean;
  processor_pid?: number;
  species_hearing?: {
    active_within_hours?: number;
    by_species?: Record<string, { active?: number }>;
  };
  species_fifo_table?: BirdnetSpeciesFifoRow[];
  species_counts?: Record<string, number>;
};

export type BirdnetFifoPayload = {
  available?: boolean;
  snapshot?: BirdnetFifoDialogSnapshot | null;
} & Record<string, unknown>;

const postSystemAction = async (
  path: string,
  body: Record<string, unknown> = {},
): Promise<Record<string, unknown>> => {
  const response = await axios.post(`${BASE_API_URL}${path}`, body, {
    withCredentials: true,
  });
  return response.data as Record<string, unknown>;
};

export const fetchFusionExportStatus = async (): Promise<SystemJobStatus> => {
  const response = await axios.get(
    `${BASE_API_URL}/system/fusion/export/status`,
    {
      withCredentials: true,
    },
  );
  return response.data as SystemJobStatus;
};

export const fetchFusionEvalStatus = async (): Promise<SystemJobStatus> => {
  const response = await axios.get(
    `${BASE_API_URL}/system/fusion/eval/status`,
    {
      withCredentials: true,
    },
  );
  return response.data as SystemJobStatus;
};

export const fetchRecognitionImprovementSummary =
  async (): Promise<RecognitionImprovementSummary> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/recognition-improvement`,
      {
        withCredentials: true,
      },
    );
    return response.data as RecognitionImprovementSummary;
  };

export const startRecognitionImprovementTrain = async (): Promise<{
  message?: string;
}> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/recognition-improvement/train`,
    {},
    { withCredentials: true },
  );
  return response.data as { message?: string };
};

export const fetchRecognitionImprovementTrainStatus =
  async (): Promise<SystemJobStatus> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/recognition-improvement/train/status`,
      { withCredentials: true },
    );
    return response.data as SystemJobStatus;
  };

export const rollbackRecognitionImprovement =
  async (): Promise<RecognitionImprovementSummary> => {
    const response = await axios.post(
      `${BASE_API_URL}/system/recognition-improvement/rollback`,
      {},
      { withCredentials: true },
    );
    return response.data as RecognitionImprovementSummary;
  };

export const startFusionExport = async (): Promise<{ message?: string }> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/fusion/export`,
    {},
    { withCredentials: true },
  );
  return response.data as { message?: string };
};

export const startFusionEval = async (): Promise<{ message?: string }> => {
  const response = await axios.post(
    `${BASE_API_URL}/system/fusion/eval`,
    {},
    { withCredentials: true },
  );
  return response.data as { message?: string };
};

export const downloadLatestFusionExport = (): void => {
  window.open(
    `${BASE_API_URL}/system/fusion/export/download`,
    '_blank',
    'noopener,noreferrer',
  );
};

/** Long-form CSV from the last successful fusion eval (section / metric / value). */
export const downloadLatestFusionEvalReport = (): void => {
  window.open(
    `${BASE_API_URL}/system/fusion/eval/download`,
    '_blank',
    'noopener,noreferrer',
  );
};

export const fetchBirdnetFifoSnapshot =
  async (): Promise<BirdnetFifoPayload> => {
    const response = await axios.get(
      `${BASE_API_URL}/system/diagnostics/birdnet-fifo`,
      {
        withCredentials: true,
      },
    );
    return response.data as BirdnetFifoPayload;
  };

export const seedSpeciesRegistry = async (): Promise<Record<string, unknown>> =>
  postSystemAction('/system/species-registry/seed');

export const backfillSpeciesRegistry = async (): Promise<
  Record<string, unknown>
> => postSystemAction('/system/species-registry/backfill', { dry_run: false });

export const enrichSpeciesRegistryMetadata = async (): Promise<
  Record<string, unknown>
> =>
  postSystemAction('/system/species-registry/enrich-metadata/start', {
    limit: 300,
    retry_failed_only: false,
  });

export const materializeSpeciesAllowlist = async (): Promise<
  Record<string, unknown>
> =>
  postSystemAction('/system/species-registry/materialize-allowlist', {
    dry_run: false,
    fill_metadata: true,
  });

export const mergeDuplicateSpecies = async (): Promise<
  Record<string, unknown>
> => postSystemAction('/system/merge-duplicate-species');

export const reconcileSpeciesCatalog = async (): Promise<
  Record<string, unknown>
> => postSystemAction('/system/species-catalog/reconcile', { dry_run: false });

/** Sync with `BROKEN_VIDEOS_PURGE_CONFIRMATION` in system_diagnostics_service.py */
export const PURGE_CONFIRM_PHRASE_BROKEN_VIDEOS_BATCH =
  'purge_all_broken_video_rows';

/** Sync with `NO_SPECIES_VIDEOS_PURGE_CONFIRMATION` in system_diagnostics_service.py */
export const PURGE_CONFIRM_PHRASE_NO_SPECIES_VIDEOS_BATCH =
  'purge_videos_without_species';

export const previewBrokenVideosPurge = async (): Promise<
  Record<string, unknown>
> =>
  postSystemAction('/system/diagnostics/broken-videos/purge', {
    dry_run: true,
    max_scan: 200_000,
  });

export const purgeBrokenVideosBatch = async (
  confirmText: string,
): Promise<Record<string, unknown>> =>
  postSystemAction('/system/diagnostics/broken-videos/purge', {
    dry_run: false,
    confirm_text: confirmText,
    limit: 500,
  });

export const previewNoSpeciesVideosPurge = async (): Promise<
  Record<string, unknown>
> =>
  postSystemAction('/system/diagnostics/no-species-videos/purge', {
    dry_run: true,
  });

export const purgeNoSpeciesVideosBatch = async (
  confirmText: string,
): Promise<Record<string, unknown>> =>
  postSystemAction('/system/diagnostics/no-species-videos/purge', {
    dry_run: false,
    confirm_text: confirmText,
    limit: 500,
  });
