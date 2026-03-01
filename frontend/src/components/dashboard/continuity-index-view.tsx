"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ContinuityIndexScore,
  RiskIndicator,
  MomentumChart,
  MilestoneCompletionProgress,
  SupervisionLatencyWidget,
  OpportunityEngagementCounter,
  WritingVelocityWidget,
  HealthTrajectoryWidget,
} from "./index";
import type { ContinuityIndexData } from "@/lib/types/continuity";

interface ContinuityIndexViewProps {
  data: ContinuityIndexData;
  className?: string;
}

export function ContinuityIndexView({ data, className }: ContinuityIndexViewProps) {
  return (
    <div className={className}>
      {/* Hero: Score + Risk */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <ContinuityIndexScore
          score={data.score}
          riskLevel={data.riskLevel}
          className="min-w-[200px]"
        />
        <RiskIndicator riskLevel={data.riskLevel} />
      </div>

      {/* Momentum chart */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Momentum</CardTitle>
          <p className="text-sm text-muted-foreground">
            Longitudinal continuity over your PhD timeline
          </p>
        </CardHeader>
        <CardContent>
          <MomentumChart data={data.momentumSeries} />
        </CardContent>
      </Card>

      {/* Metric cards grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              Milestone completion
            </CardTitle>
          </CardHeader>
          <CardContent>
            <MilestoneCompletionProgress
              completed={data.completedMilestones}
              total={data.totalMilestones}
              percent={data.milestoneCompletionPercent}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              Supervision latency
            </CardTitle>
          </CardHeader>
          <CardContent>
            <SupervisionLatencyWidget latencyDays={data.supervisionLatencyDays} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              Opportunity engagement
            </CardTitle>
          </CardHeader>
          <CardContent>
            <OpportunityEngagementCounter
              actedOn={data.opportunitiesActedOn}
              total={data.opportunitiesTotal}
              score={data.opportunityEngagementScore}
            />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">
              Writing & health
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <WritingVelocityWidget wordsPerWeek={data.writingVelocity} />
            <HealthTrajectoryWidget trajectory={data.healthTrajectory} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
