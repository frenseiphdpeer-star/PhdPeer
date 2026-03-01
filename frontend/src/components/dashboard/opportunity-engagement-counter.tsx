"use client";

import { Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";

interface OpportunityEngagementCounterProps {
  actedOn: number;
  total: number;
  score: number; // 0-100
  className?: string;
}

export function OpportunityEngagementCounter({
  actedOn,
  total,
  score,
  className,
}: OpportunityEngagementCounterProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2">
        <Sparkles className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Opportunity engagement</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold tabular-nums">{actedOn}</span>
        <span className="text-sm text-muted-foreground">/ {total} acted on</span>
      </div>
      <div className="flex items-center gap-2">
        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
          <div
            className="h-full bg-emerald-500/80"
            style={{ width: `${score}%` }}
          />
        </div>
        <span className="text-xs tabular-nums text-muted-foreground">
          {score}%
        </span>
      </div>
    </div>
  );
}
