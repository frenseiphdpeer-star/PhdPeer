"use client";

import { useQuery } from "@tanstack/react-query";
import { getTimeline } from "@/services/timeline.service";

export const timelineQueryKey = (baselineId: string) =>
  ["timeline", baselineId] as const;

export function useTimeline(baselineId: string | null) {
  return useQuery({
    queryKey: timelineQueryKey(baselineId ?? ""),
    queryFn: () => getTimeline(baselineId!),
    enabled: !!baselineId,
  });
}
