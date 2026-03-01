"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ClipboardCheck, ArrowRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ApplicationTrackerEntry, ApplicationStatus, OpportunityType } from "@/lib/types/opportunities";

const pipelineStages: ApplicationStatus[] = [
  "preparing",
  "submitted",
  "under_review",
  "accepted",
];

const statusConfig: Record<ApplicationStatus, { label: string; color: string; dot: string }> = {
  discovered:   { label: "Discovered",   color: "text-muted-foreground", dot: "bg-muted-foreground/30" },
  saved:        { label: "Saved",        color: "text-muted-foreground", dot: "bg-muted-foreground/40" },
  preparing:    { label: "Preparing",    color: "text-amber-600 dark:text-amber-400",   dot: "bg-amber-500" },
  submitted:    { label: "Submitted",    color: "text-blue-600 dark:text-blue-400",     dot: "bg-blue-500" },
  under_review: { label: "Under Review", color: "text-purple-600 dark:text-purple-400", dot: "bg-purple-500" },
  accepted:     { label: "Accepted",     color: "text-emerald-600 dark:text-emerald-400", dot: "bg-emerald-500" },
  rejected:     { label: "Not Selected", color: "text-muted-foreground",                 dot: "bg-muted-foreground/40" },
  withdrawn:    { label: "Withdrawn",    color: "text-muted-foreground",                 dot: "bg-muted-foreground/40" },
};

const typeShort: Record<OpportunityType, string> = {
  grant: "Grant",
  conference: "Conf",
  call_for_papers: "CFP",
  collaboration: "Collab",
};

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

interface ApplicationTrackerProps {
  applications: ApplicationTrackerEntry[];
  className?: string;
}

export function ApplicationTracker({ applications, className }: ApplicationTrackerProps) {
  const activeApps = applications.filter((a) =>
    ["preparing", "submitted", "under_review"].includes(a.status)
  );
  const completedApps = applications.filter((a) =>
    ["accepted", "rejected", "withdrawn"].includes(a.status)
  );

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ClipboardCheck className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Application Tracker</CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className="text-[10px] py-0 tabular-nums">
              {activeApps.length} active
            </Badge>
            <Badge variant="success" className="text-[10px] py-0 tabular-nums">
              {completedApps.filter((a) => a.status === "accepted").length} accepted
            </Badge>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pb-4">
        {/* Pipeline visualization */}
        <div className="flex items-center justify-between rounded-lg bg-muted/40 px-3 py-2.5">
          {pipelineStages.map((stage, i) => {
            const count = applications.filter((a) => a.status === stage).length;
            const cfg = statusConfig[stage];
            return (
              <div key={stage} className="flex items-center gap-2">
                <div className="flex flex-col items-center">
                  <div className={cn("h-6 w-6 rounded-full flex items-center justify-center text-[10px] font-bold text-white", cfg.dot)}>
                    {count}
                  </div>
                  <span className="mt-1 text-[10px] text-muted-foreground">{cfg.label}</span>
                </div>
                {i < pipelineStages.length - 1 && (
                  <ArrowRight className="h-3 w-3 text-muted-foreground/30 mx-1" />
                )}
              </div>
            );
          })}
        </div>

        {/* Active applications */}
        {activeApps.length > 0 && (
          <div>
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">
              In progress
            </h4>
            <div className="space-y-1.5">
              {activeApps.map((app) => {
                const cfg = statusConfig[app.status];
                return (
                  <div
                    key={app.opportunityId}
                    className="flex items-center gap-3 rounded-lg border bg-card/50 px-3 py-2"
                  >
                    <div className={cn("h-2 w-2 rounded-full shrink-0", cfg.dot)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{app.title}</p>
                      <p className="text-[10px] text-muted-foreground">{app.organization}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Badge variant="outline" className="text-[10px] py-0">
                        {typeShort[app.type]}
                      </Badge>
                      <div className="text-right">
                        <p className={cn("text-[10px] font-medium", cfg.color)}>{cfg.label}</p>
                        <p className="text-[10px] text-muted-foreground tabular-nums">
                          Due {formatDate(app.deadline)}
                        </p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Completed */}
        {completedApps.length > 0 && (
          <div>
            <h4 className="mb-2 text-xs font-medium text-muted-foreground">
              Completed
            </h4>
            <div className="space-y-1.5">
              {completedApps.map((app) => {
                const cfg = statusConfig[app.status];
                return (
                  <div
                    key={app.opportunityId}
                    className="flex items-center gap-3 rounded-lg border bg-card/50 px-3 py-2 opacity-75"
                  >
                    <div className={cn("h-2 w-2 rounded-full shrink-0", cfg.dot)} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium truncate">{app.title}</p>
                      <p className="text-[10px] text-muted-foreground">{app.organization}</p>
                    </div>
                    <Badge variant={app.status === "accepted" ? "success" : "outline"} className="text-[10px] py-0">
                      {cfg.label}
                    </Badge>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
