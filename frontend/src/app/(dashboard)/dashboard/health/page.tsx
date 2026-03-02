"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "@/components/error-boundary";
import { ChartPageSkeleton } from "@/components/skeletons";
import { healthAssessmentDummy } from "@/lib/data/health-assessment-dummy";

const HealthAssessmentView = dynamic(
  () =>
    import("@/components/health/health-assessment-view").then(
      (m) => m.HealthAssessmentView
    ),
  { loading: () => <ChartPageSkeleton /> }
);

export default function HealthPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <ErrorBoundary section="Wellness">
        <HealthAssessmentView data={healthAssessmentDummy} />
      </ErrorBoundary>
    </div>
  );
}
