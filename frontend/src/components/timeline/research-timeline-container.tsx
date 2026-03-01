"use client";

import { useTimeline } from "@/lib/hooks/use-timeline";
import { ResearchTimeline } from "./research-timeline";
import { ResearchTimelineEmpty } from "./research-timeline-empty";
import { ResearchTimelineError } from "./research-timeline-error";
import { ResearchTimelineSkeleton } from "./research-timeline-skeleton";

interface ResearchTimelineContainerProps {
  baselineId: string | null;
  showDependencyGraph?: boolean;
  className?: string;
}

export function ResearchTimelineContainer({
  baselineId,
  showDependencyGraph = true,
  className,
}: ResearchTimelineContainerProps) {
  const { data, isLoading, isError, error, refetch } = useTimeline(baselineId);

  if (!baselineId) {
    return (
      <ResearchTimelineEmpty
        message="Select a baseline to view its timeline."
        className={className}
      />
    );
  }

  if (isLoading) {
    return <ResearchTimelineSkeleton className={className} />;
  }

  if (isError) {
    return (
      <ResearchTimelineError
        message={error instanceof Error ? error.message : "Failed to load timeline."}
        onRetry={() => refetch()}
        className={className}
      />
    );
  }

  if (!data || (data.stages.length === 0 && data.milestones.length === 0)) {
    return <ResearchTimelineEmpty className={className} />;
  }

  return (
    <ResearchTimeline
      data={data}
      showDependencyGraph={showDependencyGraph}
      className={className}
    />
  );
}
