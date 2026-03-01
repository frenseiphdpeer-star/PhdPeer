"use client";

import { HealthAssessmentView } from "@/components/health";
import { healthAssessmentDummy } from "@/lib/data/health-assessment-dummy";

export default function HealthPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <HealthAssessmentView data={healthAssessmentDummy} />
    </div>
  );
}
