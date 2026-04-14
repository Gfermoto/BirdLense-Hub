import { useQuery } from '@tanstack/react-query';
import {
  fetchReadiness,
  fetchProcessorLogs,
  fetchSystemMetricsHistory,
  fetchSystemMetricsLive,
  fetchSystemVisitors,
} from '../api/api';
import { queryKeys } from '../api/queryKeys';

export function useSystemMetricsLiveQuery() {
  return useQuery({
    queryKey: queryKeys.system.metricsLive,
    queryFn: fetchSystemMetricsLive,
    refetchInterval: 5000,
  });
}

export function useSystemReadinessQuery() {
  return useQuery({
    queryKey: queryKeys.system.readiness,
    queryFn: fetchReadiness,
    refetchInterval: 30_000,
  });
}

export function useSystemMetricsHistoryQuery(hours: number) {
  return useQuery({
    queryKey: queryKeys.system.metricsHistory(hours),
    queryFn: () => fetchSystemMetricsHistory(hours),
    staleTime: 60_000,
  });
}

export function useSystemVisitorsQuery(days: number) {
  return useQuery({
    queryKey: queryKeys.system.visitors(days),
    queryFn: () => fetchSystemVisitors(days),
    staleTime: 60_000,
  });
}

export function useProcessorLogsQuery(lines: number) {
  return useQuery({
    queryKey: queryKeys.system.processorLogs(lines),
    queryFn: () => fetchProcessorLogs(lines),
    refetchInterval: 10_000,
  });
}
