"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { logger } from "@/lib/logger";
import { notify } from "@/lib/toast";

const log = logger.child("ReactQuery");

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        // Data considered fresh for 2 minutes – prevents redundant refetches
        // during rapid navigation between pages.
        staleTime: 2 * 60 * 1000,

        // Keep unused cache entries for 10 minutes before GC.
        gcTime: 10 * 60 * 1000,

        // Retry transient failures (network hiccups) up to 2 times with backoff.
        retry: (failureCount, error) => {
          // Never retry 4xx client errors (auth, validation, not-found).
          const status = (error as { statusCode?: number })?.statusCode
            ?? (error as { response?: { status?: number } })?.response?.status;
          if (status && status >= 400 && status < 500) return false;
          return failureCount < 2;
        },
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),

        refetchOnWindowFocus: false,
        refetchOnReconnect: true,
      },
      mutations: {
        retry: false,
        onError(error) {
          log.error("Mutation failed", { error: String(error) });
          notify.apiError(error);
        },
      },
    },
  });
}

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(makeQueryClient);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
