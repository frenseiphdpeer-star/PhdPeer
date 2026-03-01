"use client";

import { Calendar } from "lucide-react";
import { cn } from "@/lib/utils";

interface ResearchTimelineEmptyProps {
  className?: string;
  message?: string;
}

export function ResearchTimelineEmpty({
  className,
  message = "No timeline yet. Generate a timeline from your baseline to get started.",
}: ResearchTimelineEmptyProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-border/60 bg-muted/20 px-8 py-20 text-center",
        className
      )}
    >
      <Calendar className="mb-4 h-10 w-10 text-muted-foreground/70" />
      <h3 className="mb-1.5 text-sm font-medium text-foreground">
        No timeline
      </h3>
      <p className="max-w-xs text-sm leading-relaxed text-muted-foreground">
        {message}
      </p>
    </div>
  );
}
