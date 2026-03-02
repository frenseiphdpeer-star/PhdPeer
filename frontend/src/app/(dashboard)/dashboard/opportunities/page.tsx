"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "@/components/error-boundary";
import { PageSkeleton } from "@/components/skeletons";
import { opportunitiesDummy } from "@/lib/data/opportunities-dummy";

const OpportunityDiscoveryView = dynamic(
  () =>
    import("@/components/opportunities/opportunity-discovery-view").then(
      (m) => m.OpportunityDiscoveryView
    ),
  { loading: () => <PageSkeleton /> }
);

export default function OpportunitiesPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <ErrorBoundary section="Opportunities">
        <OpportunityDiscoveryView data={opportunitiesDummy} />
      </ErrorBoundary>
    </div>
  );
}
