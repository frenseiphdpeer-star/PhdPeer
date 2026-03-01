"use client";

import { FileText } from "lucide-react";
import { cn } from "@/lib/utils";

interface WritingVelocityWidgetProps {
  /** Words per week */
  wordsPerWeek: number;
  className?: string;
}

export function WritingVelocityWidget({
  wordsPerWeek,
  className,
}: WritingVelocityWidgetProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center gap-2">
        <FileText className="h-4 w-4 text-muted-foreground" />
        <span className="text-sm font-medium">Writing velocity</span>
      </div>
      <div className="flex items-baseline gap-2">
        <span className="text-2xl font-bold tabular-nums">
          {wordsPerWeek.toLocaleString()}
        </span>
        <span className="text-sm text-muted-foreground">words/week</span>
      </div>
    </div>
  );
}
