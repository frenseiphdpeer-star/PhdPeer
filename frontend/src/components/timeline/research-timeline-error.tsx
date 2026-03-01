"use client";

import { AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface ResearchTimelineErrorProps {
  message?: string;
  onRetry?: () => void;
  className?: string;
}

export function ResearchTimelineError({
  message = "Failed to load timeline. Please try again.",
  onRetry,
  className,
}: ResearchTimelineErrorProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center rounded-lg border border-destructive/20 bg-destructive/5 px-8 py-20 text-center",
        className
      )}
    >
      <AlertCircle className="mb-4 h-10 w-10 text-destructive/80" />
      <h3 className="mb-1.5 text-sm font-medium text-foreground">
        Something went wrong
      </h3>
      <p className="mb-4 max-w-xs text-sm leading-relaxed text-muted-foreground">
        {message}
      </p>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}
