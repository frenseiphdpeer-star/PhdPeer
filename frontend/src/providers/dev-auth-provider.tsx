"use client";

/**
 * --- AUTH TEMPORARILY BYPASSED ---
 *
 * Dev-only provider that seeds the Zustand auth store with a dev user
 * fetched from the backend. This ensures all frontend features that depend
 * on `useAuthStore().user` work correctly without a real login flow.
 *
 * Remove this provider (and its usage in providers/index.tsx) when
 * re-enabling authentication.
 */

import { useEffect, useRef, type ReactNode } from "react";
import { useAuthStore } from "@/lib/store/auth-store";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function DevAuthProvider({ children }: { children: ReactNode }) {
  const user = useAuthStore((s) => s.user);
  const setAuth = useAuthStore((s) => s.setAuth);
  const attempted = useRef(false);

  useEffect(() => {
    // Only seed once, and only when the store has no user
    if (user || attempted.current) return;
    attempted.current = true;

    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/me`);
        if (!res.ok) return;
        const data = await res.json();
        setAuth(
          {
            id: data.id,
            email: data.email,
            full_name: data.full_name ?? "Dev User",
            role: data.role ?? "researcher",
            institution: data.institution ?? null,
            field_of_study: data.field_of_study ?? null,
            is_active: data.is_active ?? true,
          },
          "dev-token",      // placeholder access token
          "dev-refresh",    // placeholder refresh token
        );
      } catch {
        // Silently fail — app still works, just without user context
      }
    })();
  }, [user, setAuth]);

  return <>{children}</>;
}
