/** Central React Query keys (#296) — invalidate via queryKeys.* for stable contracts. */

export const queryKeys = {
  settings: {
    all: ['settings'] as const,
    /** Must match useQuery keys in ProtectedAreaProvider (session gate). */
    requiresPassword: ['settings-requires-password'] as const,
    checkAccess: ['settings-check-access'] as const,
  },
  species: {
    observed: ['species', 'observed'] as const,
  },
  system: {
    metricsLive: ['system', 'metrics', 'live'] as const,
    metricsHistory: (hours: number) => ['system', 'metrics', 'history', hours] as const,
    visitors: (days: number) => ['system', 'visitors', days] as const,
    processorLogs: (lines: number) => ['system', 'processorLogs', lines] as const,
  },
} as const;
