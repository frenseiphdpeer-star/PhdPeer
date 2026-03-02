"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "@/components/error-boundary";
import { ChartPageSkeleton } from "@/components/skeletons";
import { writingEvolutionDummy } from "@/lib/data/writing-evolution-dummy";

const WritingEvolutionView = dynamic(
  () =>
    import("@/components/writing/writing-evolution-view").then(
      (m) => m.WritingEvolutionView
    ),
  { loading: () => <ChartPageSkeleton /> }
);

export default function WritingPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <ErrorBoundary section="Writing">
        <WritingEvolutionView data={writingEvolutionDummy} />
      </ErrorBoundary>
    </div>
  );
}
