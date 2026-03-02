"use client";

import { useTimeline } from "@/lib/hooks/use-timeline";
import { useMilestoneCompletion } from "@/lib/hooks/use-milestone-completion";
import { ErrorBoundary } from "@/components/error-boundary";
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
  const milestone = useMilestoneCompletion(baselineId);

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
    <ErrorBoundary section="Timeline">
      <ResearchTimeline
        data={data}
        showDependencyGraph={showDependencyGraph}
        className={className}
        onToggleMilestone={(milestoneId, completed) =>
          milestone.mutate({ milestoneId, completed })
        }
        togglingMilestoneId={
          milestone.isPending
            ? (milestone.variables?.milestoneId ?? null)
            : null
        }
      />
    </ErrorBoundary>
  );
}
