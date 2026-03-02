"use client";

import { useMemo } from "react";
import { Accordion } from "@/components/ui/accordion";
import { GitBranch, LayoutList } from "lucide-react";
import type { TimelineResponse, TimelineMilestone } from "@/lib/types";
import { TimelineStageCard } from "./timeline-stage-card";
import { TimelineDependencyGraph } from "./timeline-dependency-graph";
import { cn } from "@/lib/utils";

interface ResearchTimelineProps {
  data: TimelineResponse;
  showDependencyGraph?: boolean;
  className?: string;
  onToggleMilestone?: (milestoneId: string, completed: boolean) => void;
  togglingMilestoneId?: string | null;
}

function groupMilestonesByStage(
  stages: TimelineResponse["stages"],
  milestones: TimelineMilestone[]
): Map<string, TimelineMilestone[]> {
  const map = new Map<string, TimelineMilestone[]>();
  stages.forEach((s) => map.set(s.id, []));

  milestones.forEach((m) => {
    const stageId = m.stage_id || stages[0]?.id;
    if (stageId && map.has(stageId)) {
      map.get(stageId)!.push(m);
    } else if (stages.length > 0) {
      map.get(stages[0].id)!.push(m);
    }
  });

  map.forEach((list) =>
    list.sort((a, b) => a.milestone_order - b.milestone_order)
  );
  return map;
}

export function ResearchTimeline({
  data,
  showDependencyGraph = true,
  className,
  onToggleMilestone,
  togglingMilestoneId,
}: ResearchTimelineProps) {
  const milestonesByStage = useMemo(
    () => groupMilestonesByStage(data.stages, data.milestones),
    [data.stages, data.milestones]
  );

  const sortedStages = useMemo(
    () => [...data.stages].sort((a, b) => a.stage_order - b.stage_order),
    [data.stages]
  );

  return (
    <div className={cn("space-y-8", className)}>
      {showDependencyGraph &&
        data.dependencies.length > 0 && (
          <section>
            <h3 className="mb-3 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
              <GitBranch className="h-3.5 w-3.5" />
              Dependencies
            </h3>
            <TimelineDependencyGraph
              stages={data.stages}
              milestones={data.milestones}
              dependencies={data.dependencies}
            />
          </section>
        )}

      <section>
        <h3 className="mb-4 flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
          <LayoutList className="h-3.5 w-3.5" />
          Timeline
        </h3>
        <Accordion type="multiple" className="space-y-2">
          {sortedStages.map((stage) => (
            <TimelineStageCard
              key={stage.id}
              stage={stage}
              milestones={milestonesByStage.get(stage.id) ?? []}
              value={stage.id}
              onToggleMilestone={onToggleMilestone}
              togglingMilestoneId={togglingMilestoneId}
            />
          ))}
        </Accordion>
      </section>
    </div>
  );
}
