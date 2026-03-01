"use client";

import { useQuery } from "@tanstack/react-query";
import type { ContinuityIndexData } from "@/lib/types/continuity";
import { continuityDummyData } from "@/lib/data/continuity-dummy";

export const continuityQueryKey = ["continuity-index"] as const;

/**
 * Fetch continuity index data.
 * Replace with real API call when backend endpoint is ready.
 */
async function fetchContinuityIndex(): Promise<ContinuityIndexData> {
  // TODO: Replace with apiClient.get("/analytics/continuity") or similar
  return Promise.resolve(continuityDummyData);
}

export function useContinuityIndex() {
  return useQuery({
    queryKey: continuityQueryKey,
    queryFn: fetchContinuityIndex,
  });
}
