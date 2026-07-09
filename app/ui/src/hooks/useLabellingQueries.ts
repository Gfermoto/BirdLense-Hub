import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  exportLabellingCases,
  fetchLabellingCases,
  mineLabellingCases,
  patchLabellingCase,
  postLabellingBatchFeedback,
  postLabellingFeedback,
  type LabellingBatchOperation,
  type LabellingCaseStatus,
} from '../api/labelling';
import { queryKeys } from '../api/queryKeys';

export function useLabellingCasesQuery(
  status: LabellingCaseStatus | 'all',
  limit = 120,
  withMediaOnly = true,
) {
  return useQuery({
    queryKey: queryKeys.labelling.cases(status, withMediaOnly),
    queryFn: () => fetchLabellingCases(status, limit, withMediaOnly),
    refetchInterval: 30_000,
  });
}

export function useMineLabellingCasesMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: mineLabellingCases,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.labelling.casesAll });
    },
  });
}

export function usePatchLabellingCaseMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, note }: { id: number; status: LabellingCaseStatus; note?: string }) =>
      patchLabellingCase(id, status, note),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.labelling.casesAll });
    },
  });
}

export function useExportLabellingCasesMutation() {
  return useMutation({
    mutationFn: ({ format, status }: { format: 'yolo' | 'coco'; status?: LabellingCaseStatus }) =>
      exportLabellingCases(format, status || 'approved'),
  });
}

export function useLabellingFeedbackMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      id,
      action,
      species_tag,
    }: {
      id: number;
      action: 'reject_box' | 'tag_species' | 'flag_semantic_error';
      species_tag?: string;
    }) => postLabellingFeedback(id, { action, species_tag }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.labelling.casesAll });
    },
  });
}

export function useLabellingBatchFeedbackMutation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (operations: LabellingBatchOperation[]) => postLabellingBatchFeedback(operations),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.labelling.casesAll });
    },
  });
}
