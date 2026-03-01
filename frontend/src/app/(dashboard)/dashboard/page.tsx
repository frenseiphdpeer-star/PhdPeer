"use client";

import { ContinuityIndexView } from "@/components/dashboard/continuity-index-view";
import { continuityDummyData } from "@/lib/data/continuity-dummy";

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

      <ContinuityIndexView data={continuityDummyData} />
    </div>
  );
}
