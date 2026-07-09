import { describe, expect, it, beforeEach } from 'vitest';
import {
  loadSettingsTier,
  normalizeSettingsTier,
  saveSettingsTier,
  showAdvancedProcessorBlocks,
  showExpertTools,
  SETTINGS_TIER_STORAGE_KEY,
} from './settingsTier';

describe('settingsTier', () => {
  beforeEach(() => {
    localStorage.removeItem(SETTINGS_TIER_STORAGE_KEY);
  });

  it('normalizes legacy simple to basic', () => {
    expect(normalizeSettingsTier('simple')).toBe('basic');
    expect(normalizeSettingsTier('advanced')).toBe('advanced');
    expect(normalizeSettingsTier('expert')).toBe('expert');
  });

  it('persists tier in localStorage', () => {
    saveSettingsTier('expert');
    expect(loadSettingsTier()).toBe('expert');
  });

  it('gates advanced and expert blocks', () => {
    expect(showAdvancedProcessorBlocks('basic')).toBe(false);
    expect(showAdvancedProcessorBlocks('advanced')).toBe(true);
    expect(showExpertTools('advanced')).toBe(false);
    expect(showExpertTools('expert')).toBe(true);
  });
});
