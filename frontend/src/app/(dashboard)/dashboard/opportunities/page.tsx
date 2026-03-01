"use client";

import { OpportunityDiscoveryView } from "@/components/opportunities";
import { opportunitiesDummy } from "@/lib/data/opportunities-dummy";

export default function OpportunitiesPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <OpportunityDiscoveryView data={opportunitiesDummy} />
    </div>
  );
}
