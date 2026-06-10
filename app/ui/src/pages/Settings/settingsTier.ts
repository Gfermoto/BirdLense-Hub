/** Settings page visibility tiers (#623 / consortium 2.4). */

export type SettingsTier = 'basic' | 'advanced' | 'expert';

export const SETTINGS_TIER_STORAGE_KEY = 'birdlense.settingsTier';

const VALID_TIERS: SettingsTier[] = ['basic', 'advanced', 'expert'];

export function normalizeSettingsTier(raw: string | null | undefined): SettingsTier {
  if (raw === 'advanced' || raw === 'expert') return raw;
  if (raw === 'basic' || raw === 'simple') return 'basic';
  return 'basic';
}

export function loadSettingsTier(): SettingsTier {
  try {
    return normalizeSettingsTier(localStorage.getItem(SETTINGS_TIER_STORAGE_KEY));
  } catch {
    return 'basic';
  }
}

export function saveSettingsTier(tier: SettingsTier): void {
  localStorage.setItem(SETTINGS_TIER_STORAGE_KEY, tier);
}

export function isBasicTier(tier: SettingsTier): boolean {
  return tier === 'basic';
}

export function showAdvancedProcessorBlocks(tier: SettingsTier): boolean {
  return tier === 'advanced' || tier === 'expert';
}

export function showExpertTools(tier: SettingsTier): boolean {
  return tier === 'expert';
}

export function isValidSettingsTier(value: string): value is SettingsTier {
  return (VALID_TIERS as string[]).includes(value);
}
