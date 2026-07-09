/** Maps backend operational_tier to MUI Alert/Chip severity. */
export type OperationalTier = 'ok' | 'info' | 'warning' | 'critical';

export function operationalTierSeverity(
  tier: string | undefined,
): 'success' | 'info' | 'warning' | 'error' {
  if (tier === 'ok') return 'success';
  if (tier === 'info') return 'info';
  if (tier === 'warning') return 'warning';
  if (tier === 'critical') return 'error';
  return 'info';
}
