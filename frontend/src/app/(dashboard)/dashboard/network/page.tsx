"use client";

import { NetworkIntelligenceView } from "@/components/network";
import { networkDummy } from "@/lib/data/network-dummy";

export default function NetworkPage() {
  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      <NetworkIntelligenceView data={networkDummy} />
    </div>
  );
}
