"use client";

import { QueryProvider } from "./query-provider";
import { ThemeProvider } from "./theme-provider";
import { DevAuthProvider } from "./dev-auth-provider";
import type { ReactNode } from "react";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider>
      <QueryProvider>
        {/* --- AUTH TEMPORARILY BYPASSED --- Remove DevAuthProvider when re-enabling auth */}
        <DevAuthProvider>{children}</DevAuthProvider>
      </QueryProvider>
    </ThemeProvider>
  );
}
