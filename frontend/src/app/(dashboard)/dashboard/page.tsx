"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "@/components/error-boundary";
import { DashboardSkeleton } from "@/components/skeletons";
import { continuityDummyData } from "@/lib/data/continuity-dummy";

const ContinuityIndexView = dynamic(
  () =>
    import("@/components/dashboard/continuity-index-view").then(
      (m) => m.ContinuityIndexView
    ),
  { loading: () => <DashboardSkeleton /> }
);

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">
          Research Dashboard
        </h2>
        <p className="text-muted-foreground">
          Continuity Index — longitudinal tracking across your PhD journey
        </p>
      </div>

      <ErrorBoundary section="Dashboard">
        <ContinuityIndexView data={continuityDummyData} />
      </ErrorBoundary>
    </div>
  );
}
