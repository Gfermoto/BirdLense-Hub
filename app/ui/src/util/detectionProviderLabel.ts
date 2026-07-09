import type { TFunction } from 'i18next';

/** Human-facing detector source label; public view hides internal product names. */
export function detectionProviderLabel(
  t: TFunction,
  provider: string,
  options?: { technical?: boolean },
): string {
  const technical = options?.technical !== false;
  const key = String(provider || '').trim().toLowerCase();
  if (!technical) {
    if (key === 'yolo') return t('video.detectionProviderYoloPublic');
    if (key === 'frigate') return t('video.detectionProviderFrigatePublic');
    if (key === 'birdnet_mqtt') return t('video.detectionProviderBirdnetPublic');
    return key || '—';
  }
  if (key === 'yolo') return t('video.detectionProviderYolo');
  if (key === 'frigate') return t('video.detectionProviderFrigate');
  if (key === 'birdnet_mqtt') return t('video.detectionProviderBirdnetMqtt');
  return provider;
}
