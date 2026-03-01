"use client";

import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

interface SupervisionLatencyWidgetProps {
  /** Average days since last supervision meeting */
  latencyDays: number;
  className?: string;
}

export function SupervisionLatencyWidget({
  latencyDays,
  className,
}: SupervisionLatencyWidgetProps) {
  const status =
    latencyDays <= 7 ? "healthy" : latencyDays <= 14 ? "moderate" : "high";

  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2">
        <Calendar className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Supervision latency</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold tabular-nums">{latencyDays}</span>
        <span className="text-sm text-muted-foreground">days avg</span>
      </div>
      <p
        className={cn(
          "text-xs",
          status === "healthy" && "text-emerald-600 dark:text-emerald-500",
          status === "moderate" && "text-amber-600 dark:text-amber-500",
          status === "high" && "text-destructive"
        )}
      >
        {status === "healthy" && "Meeting regularly"}
        {status === "moderate" && "Consider scheduling meeting"}
        {status === "high" && "Schedule meeting soon"}
      </p>
    </div>
  );
}
