"use client";

import { CheckCircle2, Circle, Flag } from "lucide-react";
import type { TimelineMilestone } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TimelineMilestoneItemProps {
  milestone: TimelineMilestone;
  className?: string;
}

export function TimelineMilestoneItem({
  milestone,
  className,
}: TimelineMilestoneItemProps) {
  return (
    <div
      className={cn(
        "flex items-start gap-3 rounded-md px-3 py-2 text-sm transition-colors",
        milestone.is_critical && "bg-amber-50/50 dark:bg-amber-950/20",
        className
      )}
    >
      <span className="mt-0.5 shrink-0 text-muted-foreground">
        {milestone.is_completed ? (
          <CheckCircle2 className="h-4 w-4 text-emerald-600 dark:text-emerald-500" />
        ) : (
          <Circle className="h-4 w-4" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-medium text-foreground">{milestone.title}</span>
          {milestone.is_critical && (
            <Flag className="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-500" />
          )}
        </div>
        {milestone.description && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            {milestone.description}
          </p>
        )}
      </div>
    </div>
  );
}
