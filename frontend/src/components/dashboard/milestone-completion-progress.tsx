"use client";

import { Progress } from "@/components/ui/progress";
import { CheckCircle2, Circle } from "lucide-react";
import { cn } from "@/lib/utils";

interface MilestoneCompletionProgressProps {
  completed: number;
  total: number;
  percent: number;
  className?: string;
}

export function MilestoneCompletionProgress({
  completed,
  total,
  percent,
  className,
}: MilestoneCompletionProgressProps) {
  return (
    <div className={cn("space-y-3", className)}>
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">Milestone completion</span>
        <span className="text-sm tabular-nums text-muted-foreground">
          {completed} / {total}
        </span>
      </div>
      <Progress value={percent} className="h-2.5" />
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
          {completed} completed
        </span>
        <span className="flex items-center gap-1.5">
          <Circle className="h-3.5 w-3.5" />
          {total - completed} remaining
        </span>
      </div>
    </div>
  );
}
