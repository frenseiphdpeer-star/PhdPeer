"use client";

import { Sparkles, Bookmark, Send, Trophy, Target } from "lucide-react";
import { cn } from "@/lib/utils";
import type { OpportunityStats } from "@/lib/types/opportunities";

interface OpportunityStatsBarProps {
  stats: OpportunityStats;
  className?: string;
}

const statItems = [
  { key: "totalDiscovered" as const, label: "Discovered",  icon: Sparkles },
  { key: "saved" as const,           label: "Saved",       icon: Bookmark },
  { key: "applied" as const,         label: "Applied",     icon: Send },
  { key: "accepted" as const,        label: "Accepted",    icon: Trophy },
  { key: "avgMatchScore" as const,   label: "Avg. Match",  icon: Target },
];

export function OpportunityStatsBar({ stats, className }: OpportunityStatsBarProps) {
  return (
    <div className={cn(
      "grid grid-cols-2 gap-3 sm:grid-cols-5",
      className
    )}>
      {statItems.map(({ key, label, icon: Icon }) => {
        const value = stats[key];
        const isPercentage = key === "avgMatchScore";
        return (
          <div
            key={key}
            className="flex items-center gap-3 rounded-xl border bg-card px-4 py-3"
          >
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-muted">
              <Icon className="h-4 w-4 text-muted-foreground" />
            </div>
            <div>
              <p className="text-lg font-bold tabular-nums leading-none">
                {value}{isPercentage ? "%" : ""}
              </p>
              <p className="mt-0.5 text-[10px] text-muted-foreground">{label}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
