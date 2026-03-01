"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Users, Shield, Building2, UserCheck, UserX } from "lucide-react";
import { cn } from "@/lib/utils";
import { ResponseLatencyCard } from "./response-latency-card";
import { FeedbackTimeline } from "./feedback-timeline";
import { EngagementQualityScore } from "./engagement-quality-score";
import { SupervisorBenchmark } from "./supervisor-benchmark";
import { BottleneckAlerts } from "./bottleneck-alerts";
import type { SupervisionIntelligenceData, SupervisionMode } from "@/lib/types/supervision";

interface SupervisionIntelligenceViewProps {
  data: SupervisionIntelligenceData;
  mode: SupervisionMode;
  className?: string;
}

function InstitutionOverview({ data }: { data: SupervisionIntelligenceData }) {
  const agg = data.institutionAggregate;
  if (!agg) return null;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Building2 className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Institution Overview</CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Summary stats */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: "Researchers", value: agg.totalResearchers, icon: Users },
            { label: "Supervisors", value: agg.totalSupervisors, icon: UserCheck },
            { label: "On Track", value: agg.researchersOnTrack, icon: UserCheck, color: "text-emerald-600 dark:text-emerald-400" },
            { label: "Needs Support", value: agg.researchersAtRisk, icon: UserX, color: "text-amber-600 dark:text-amber-400" },
          ].map((stat) => {
            const Icon = stat.icon;
            return (
              <div key={stat.label} className="rounded-lg bg-muted/50 p-3">
                <div className="flex items-center gap-1.5 mb-1">
                  <Icon className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                    {stat.label}
                  </span>
                </div>
                <p className={cn("text-2xl font-bold tabular-nums", stat.color)}>{stat.value}</p>
              </div>
            );
          })}
        </div>

        <Separator />

        {/* Supervisor caseload table */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
            Supervisor caseload summary
          </h4>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="pb-2 pr-4 font-medium">Supervisor</th>
                  <th className="pb-2 pr-4 font-medium text-right">Students</th>
                  <th className="pb-2 pr-4 font-medium text-right">Avg latency</th>
                  <th className="pb-2 font-medium text-right">Engagement</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {agg.supervisorDistribution.map((sup) => (
                  <tr key={sup.name} className="group">
                    <td className="py-2 pr-4 font-medium">{sup.name}</td>
                    <td className="py-2 pr-4 text-right tabular-nums text-muted-foreground">
                      {sup.activeStudents}
                    </td>
                    <td className="py-2 pr-4 text-right">
                      <span className={cn(
                        "tabular-nums font-medium",
                        sup.avgLatencyDays <= 5
                          ? "text-emerald-600 dark:text-emerald-400"
                          : sup.avgLatencyDays <= 10
                            ? "text-amber-600 dark:text-amber-400"
                            : "text-red-600 dark:text-red-400"
                      )}>
                        {sup.avgLatencyDays}d
                      </span>
                    </td>
                    <td className="py-2 text-right">
                      <span className={cn(
                        "tabular-nums font-medium",
                        sup.engagementScore >= 75
                          ? "text-emerald-600 dark:text-emerald-400"
                          : sup.engagementScore >= 60
                            ? "text-amber-600 dark:text-amber-400"
                            : "text-red-600 dark:text-red-400"
                      )}>
                        {sup.engagementScore}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <p className="rounded-lg border border-dashed px-3 py-2 text-[10px] text-muted-foreground leading-relaxed">
          Supervisor names shown to authorized administrators only. Reports generated for governance use
          anonymized identifiers unless explicit consent is recorded.
        </p>
      </CardContent>
    </Card>
  );
}

export function SupervisionIntelligenceView({
  data,
  mode,
  className,
}: SupervisionIntelligenceViewProps) {
  const isInstitution = mode === "institution";

  return (
    <div className={className}>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <Users className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-bold tracking-tight">Supervision Intelligence</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            {isInstitution
              ? "Institutional oversight of supervision quality and researcher support"
              : "Understand and optimize your supervision experience"}
          </p>
        </div>
        <div className="flex items-center gap-2 self-start">
          <Badge
            variant={isInstitution ? "default" : "secondary"}
            className="text-xs"
          >
            {isInstitution ? "Institution Admin" : "Researcher View"}
          </Badge>
          <Badge
            variant="outline"
            className="flex items-center gap-1.5 border-dashed text-xs text-muted-foreground"
          >
            <Shield className="h-3 w-3" />
            Governance-ready
          </Badge>
        </div>
      </div>

      <Separator className="mb-6" />

      {/* Institution aggregate (admin only) */}
      {isInstitution && data.institutionAggregate && (
        <div className="mb-6">
          <InstitutionOverview data={data} />
        </div>
      )}

      {/* Main grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Left column */}
        <div className="space-y-6">
          <ResponseLatencyCard latency={data.latency} mode={mode} />
          <EngagementQualityScore engagement={data.engagement} mode={mode} />
        </div>

        {/* Right column */}
        <div className="space-y-6">
          <FeedbackTimeline events={data.feedbackEvents} mode={mode} />
        </div>
      </div>

      {/* Full-width sections */}
      <div className="mt-6 space-y-6">
        <SupervisorBenchmark benchmark={data.benchmark} mode={mode} />
        <BottleneckAlerts alerts={data.alerts} mode={mode} />
      </div>
    </div>
  );
}
