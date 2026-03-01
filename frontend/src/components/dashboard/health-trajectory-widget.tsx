"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

interface HealthTrajectoryWidgetProps {
  /** -1 (declining) to 1 (improving) */
  trajectory: number;
  className?: string;
}

export function HealthTrajectoryWidget({
  trajectory,
  className,
}: HealthTrajectoryWidgetProps) {
  const direction =
    trajectory > 0.1 ? "up" : trajectory < -0.1 ? "down" : "stable";

  return (
    <div className={cn("space-y-2", className)}>
      <span className="text-sm font-medium">Health trajectory</span>
      <div className="flex items-center gap-2">
        {direction === "up" && (
          <TrendingUp className="h-5 w-5 text-emerald-500" />
        )}
        {direction === "down" && (
          <TrendingDown className="h-5 w-5 text-destructive" />
        )}
        {direction === "stable" && (
          <Minus className="h-5 w-5 text-muted-foreground" />
        )}
        <span
          className={cn(
            "text-sm font-medium",
            direction === "up" && "text-emerald-600 dark:text-emerald-500",
            direction === "down" && "text-destructive",
            direction === "stable" && "text-muted-foreground"
          )}
        >
          {direction === "up" && "Improving"}
          {direction === "down" && "Declining"}
          {direction === "stable" && "Stable"}
        </span>
      </div>
    </div>
  );
}
