"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient, throwApiError } from "@/lib/api";
import { notify } from "@/lib/toast";
import type { TimelineResponse, TimelineMilestone } from "@/lib/types";
import { timelineQueryKey } from "./use-timeline";

async function toggleMilestoneCompletion(
  milestoneId: string,
  completed: boolean
): Promise<TimelineMilestone> {
  try {
    const { data } = await apiClient.patch<TimelineMilestone>(
      `/timeline/milestones/${milestoneId}`,
      { is_completed: completed }
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}

/**
 * Optimistic milestone toggle.
 *
 * Immediately flips `is_completed` in the cache, then reconciles with the
 * server response. On failure the cache is rolled back and the user is
 * notified via toast.
 */
export function useMilestoneCompletion(baselineId: string | null) {
  const queryClient = useQueryClient();
  const key = timelineQueryKey(baselineId ?? "");

  return useMutation({
    mutationFn: ({
      milestoneId,
      completed,
    }: {
      milestoneId: string;
      completed: boolean;
    }) => toggleMilestoneCompletion(milestoneId, completed),

    // ---------- Optimistic update ----------
    onMutate: async ({ milestoneId, completed }) => {
      await queryClient.cancelQueries({ queryKey: key });

      const previous = queryClient.getQueryData<TimelineResponse>(key);

      queryClient.setQueryData<TimelineResponse>(key, (old) => {
        if (!old) return old;
        return {
          ...old,
          milestones: old.milestones.map((m) =>
            m.id === milestoneId ? { ...m, is_completed: completed } : m
          ),
        };
      });

      return { previous };
    },

    // ---------- Rollback on error ----------
    onError: (_error, _vars, context) => {
      if (context?.previous) {
        queryClient.setQueryData(key, context.previous);
      }
      notify.error("Failed to update milestone");
    },

    // ---------- Reconcile with server ----------
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: key });
    },

    onSuccess: (_data, { completed }) => {
      notify.success(
        completed ? "Milestone completed!" : "Milestone reopened"
      );
    },
  });
}
