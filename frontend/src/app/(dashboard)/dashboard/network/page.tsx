"use client";

import dynamic from "next/dynamic";
import { ErrorBoundary } from "@/components/error-boundary";
import { GraphPageSkeleton } from "@/components/skeletons";
import { networkDummy } from "@/lib/data/network-dummy";

const NetworkIntelligenceView = dynamic(
  () =>
    import("@/components/network/network-intelligence-view").then(
      (m) => m.NetworkIntelligenceView
    ),
  { loading: () => <GraphPageSkeleton /> }
);

export default function NetworkPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <ErrorBoundary section="Network">
        <NetworkIntelligenceView data={networkDummy} />
      </ErrorBoundary>
    </div>
  );
}
