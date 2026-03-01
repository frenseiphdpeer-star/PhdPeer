"use client";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Network } from "lucide-react";
import { NetworkGraph } from "./network-graph";
import { CollaborationStrength } from "./collaboration-strength";
import { NetworkGapDetection } from "./network-gap-detection";
import { SuggestedCollaborators } from "./suggested-collaborators";
import type { NetworkIntelligenceData } from "@/lib/types/network";

interface NetworkIntelligenceViewProps {
  data: NetworkIntelligenceData;
  className?: string;
}

export function NetworkIntelligenceView({ data, className }: NetworkIntelligenceViewProps) {
  return (
    <div className={className}>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <Network className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-bold tracking-tight">Network Intelligence</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Visualize your research network, discover gaps, and find strategic collaborators
          </p>
        </div>
        <Badge
          variant="outline"
          className="flex items-center gap-1.5 self-start border-dashed text-xs text-muted-foreground"
        >
          <Network className="h-3 w-3" />
          Graph analysis
        </Badge>
      </div>

      <Separator className="mb-6" />

      {/* Network graph — full width */}
      <NetworkGraph
        researchers={data.researchers}
        edges={data.edges}
        clusters={data.clusters}
        institutionColors={data.institutionColors}
        className="mb-6"
      />

      {/* Two-column layout: metrics + gaps | suggestions */}
      <div className="grid gap-6 lg:grid-cols-2">
        <div className="space-y-6">
          <CollaborationStrength metrics={data.metrics} />
          <NetworkGapDetection gaps={data.gaps} />
        </div>
        <div>
          <SuggestedCollaborators collaborators={data.suggestedCollaborators} />
        </div>
      </div>
    </div>
  );
}
