"use client";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import type { TimelineStage, TimelineMilestone } from "@/lib/types";
import { TimelineMilestoneItem } from "./timeline-milestone-item";

interface TimelineStageCardProps {
  stage: TimelineStage;
  milestones: TimelineMilestone[];
  value: string;
  onToggleMilestone?: (milestoneId: string, completed: boolean) => void;
  togglingMilestoneId?: string | null;
}

const STATUS_VARIANTS: Record<string, "default" | "secondary" | "success" | "warning" | "destructive"> = {
  completed: "success",
  in_progress: "default",
  not_started: "secondary",
  delayed: "warning",
};

function getStatusVariant(status: string) {
  const normalized = status.toLowerCase().replace(/\s+/g, "_");
  return STATUS_VARIANTS[normalized] ?? "secondary";
}

export function TimelineStageCard({
  stage,
  milestones,
  value,
  onToggleMilestone,
  togglingMilestoneId,
}: TimelineStageCardProps) {
  const statusVariant = getStatusVariant(stage.status);
  const confidence = stage.confidence ?? null;
  const duration =
    stage.duration_months != null
      ? `${stage.duration_months} mo`
      : null;

  return (
    <AccordionItem value={value} className="border-none">
      <Card className="overflow-hidden border-border/60 transition-colors hover:border-border">
        <Accordion type="single" collapsible className="w-full">
          <AccordionItem value={value} className="border-none">
            <AccordionTrigger className="px-4 py-3.5 hover:no-underline [&[data-state=open]]:border-b [&[data-state=open]]:border-border/60">
              <div className="flex flex-1 flex-wrap items-center gap-4 text-left">
                <span className="font-semibold text-foreground">
                  {stage.title}
                </span>
                <div className="flex items-center gap-2">
                  {duration && (
                    <span className="text-xs text-muted-foreground">
                      {duration}
                    </span>
                  )}
                  <Badge variant={statusVariant} className="text-xs">
                    {stage.status.replace(/_/g, " ")}
                  </Badge>
                  {confidence != null && (
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-muted-foreground">
                        {confidence}%
                      </span>
                      <Progress
                        value={confidence}
                        className="h-1.5 w-16"
                      />
                    </div>
                  )}
                </div>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <CardContent className="space-y-3 px-4 pt-2 pb-4">
                {stage.description && (
                  <p className="text-sm text-muted-foreground">
                    {stage.description}
                  </p>
                )}
                {milestones.length > 0 ? (
                  <div className="space-y-1">
                    <p className="text-xs font-medium text-muted-foreground">
                      Milestones
                    </p>
                    <div className="space-y-1">
                      {milestones.map((m) => (
                        <TimelineMilestoneItem
                          key={m.id}
                          milestone={m}
                          onToggle={onToggleMilestone}
                          isToggling={togglingMilestoneId === m.id}
                        />
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground">
                    No milestones yet
                  </p>
                )}
              </CardContent>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </Card>
    </AccordionItem>
  );
}
