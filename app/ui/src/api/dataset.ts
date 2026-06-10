import {
  BASE_API_URL,
  apiBlob,
  apiFetch,
  triggerBlobDownload,
} from './client';

/** Export dataset crops as ZIP. Requires settings access. */
export const exportDataset = async (params?: {
  start_date?: string;
  end_date?: string;
  only_manually_corrected?: boolean;
  ready_for_train?: boolean;
  test_ratio?: number;
  strict_quality?: boolean;
}): Promise<void> => {
  const q = new URLSearchParams();
  if (params?.start_date) q.set('start_date', params.start_date);
  if (params?.end_date) q.set('end_date', params.end_date);
  if (params?.only_manually_corrected) q.set('only_manually_corrected', '1');
  if (params?.ready_for_train) q.set('ready_for_train', '1');
  if (params?.test_ratio != null && params.test_ratio > 0) {
    q.set('test_ratio', String(params.test_ratio));
  }
  if (params?.strict_quality) q.set('strict_quality', '1');
  const url = `${BASE_API_URL}/dataset/export${q.toString() ? `?${q}` : ''}`;
  const { blob, filename } = await apiBlob(url);
  triggerBlobDownload(blob, filename || 'birdlense_dataset.zip');
};

/** Retro-export: extract crops from all video detections into dataset. */
export const retroExportDataset = async (
  minConfidence = 0,
  period?: { start_date?: string; end_date?: string },
  onlyManuallyCorrected = false,
  rebuild = false,
): Promise<{
  saved: number;
  skipped: number;
  skipped_no_bbox?: number;
  deleted?: number;
  errors: string[];
}> => {
  const body: Record<string, unknown> = { min_confidence: minConfidence };
  if (period?.start_date) body.start_date = period.start_date;
  if (period?.end_date) body.end_date = period.end_date;
  if (onlyManuallyCorrected) body.only_manually_corrected = true;
  if (rebuild) body.rebuild = true;
  return apiFetch(`${BASE_API_URL}/dataset/retro-export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
};

/** Clean dataset: remove suspected full-frame and/or orphaned files. */
export const cleanDataset = async (params?: {
  dry_run?: boolean;
  remove_fullframe?: boolean;
  remove_orphaned?: boolean;
}): Promise<{
  deleted_fullframe: number;
  deleted_orphaned: number;
  errors: string[];
  dry_run: boolean;
}> =>
  apiFetch(`${BASE_API_URL}/dataset/clean`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params || {}),
  });

/** Download detection crop for iNaturalist. Opens iNaturalist upload in new tab. */
export const downloadDetectionCropForINaturalist = async (
  detectionId: number,
  speciesName: string,
): Promise<void> => {
  const { blob, filename } = await apiBlob(
    `${BASE_API_URL}/detections/${detectionId}/crop`,
  );
  triggerBlobDownload(
    blob,
    filename || `${speciesName.replace(/\s+/g, '_')}.jpg`,
  );
  window.open(
    'https://www.inaturalist.org/observations/upload',
    '_blank',
    'noopener',
  );
};
