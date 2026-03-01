"use client";

import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types/continuity";

interface ContinuityIndexScoreProps {
  score: number;
  riskLevel: RiskLevel;
  className?: string;
}

export function ContinuityIndexScore({
  score,
  riskLevel,
  className,
}: ContinuityIndexScoreProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-xl border bg-card px-8 py-6",
        className
      )}
    >
      <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
        Continuity Index
      </p>
      <p
        className={cn(
          "text-5xl font-bold tabular-nums",
          riskLevel === "low" && "text-emerald-600 dark:text-emerald-500",
          riskLevel === "medium" && "text-amber-600 dark:text-amber-500",
          riskLevel === "high" && "text-destructive"
        )}
      >
        {score}
      </p>
      <p className="mt-1 text-xs text-muted-foreground">out of 100</p>
    </div>
  );
}
