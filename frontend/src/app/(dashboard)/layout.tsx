"use client";

import { Suspense } from "react";
import { AppLayout } from "@/components/layout";
import { AuthGuard } from "@/components/auth-guard";
import { ErrorBoundary } from "@/components/error-boundary";
import { DashboardSkeleton } from "@/components/skeletons";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <AppLayout>
        <ErrorBoundary section="Application">
          <Suspense fallback={<DashboardSkeleton />}>{children}</Suspense>
        </ErrorBoundary>
      </AppLayout>
    </AuthGuard>
  );
}
