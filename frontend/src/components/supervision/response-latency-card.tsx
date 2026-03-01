"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Clock, TrendingDown, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { LatencyMetrics, SupervisionMode } from "@/lib/types/supervision";

interface ResponseLatencyCardProps {
  latency: LatencyMetrics;
  mode: SupervisionMode;
  className?: string;
}

function latencyStatus(days: number) {
  if (days <= 5) return { label: "Healthy", color: "text-emerald-600 dark:text-emerald-400", bg: "bg-emerald-500/10" };
  if (days <= 10) return { label: "Moderate", color: "text-amber-600 dark:text-amber-400", bg: "bg-amber-500/10" };
  return { label: "Needs attention", color: "text-red-600 dark:text-red-400", bg: "bg-red-500/10" };
}

export function ResponseLatencyCard({ latency, mode, className }: ResponseLatencyCardProps) {
  const status = latencyStatus(latency.currentAvgDays);
  const improving = latency.trend < 0;
  const TrendIcon = improving ? TrendingDown : TrendingUp;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">
              {mode === "researcher" ? "Response Latency" : "Avg. Response Latency"}
            </CardTitle>
          </div>
          <Badge
            variant="outline"
            className={cn("text-[10px] border-0", status.bg, status.color)}
          >
            {status.label}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "researcher"
            ? "Average time to receive supervisor feedback"
            : "Average feedback response time across all supervisors"}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Hero metric */}
        <div className="flex items-end gap-3">
          <div>
            <span className="text-4xl font-bold tabular-nums">{latency.currentAvgDays}</span>
            <span className="ml-1 text-sm text-muted-foreground">days</span>
          </div>
          <div className="mb-1 flex items-center gap-1">
            <TrendIcon className={cn(
              "h-3.5 w-3.5",
              improving ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
            )} />
            <span className={cn(
              "text-xs font-medium",
              improving ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"
            )}>
              {Math.abs(latency.trend).toFixed(1)}% {improving ? "faster" : "slower"}
            </span>
            <span className="text-xs text-muted-foreground">vs prev. period</span>
          </div>
        </div>

        {/* Distribution stats */}
        <div className="flex gap-4 rounded-lg bg-muted/50 px-3 py-2.5">
          <div className="flex-1">
            <p className="text-[11px] text-muted-foreground">Median</p>
            <p className="text-sm font-semibold tabular-nums">{latency.medianDays}d</p>
          </div>
          <div className="w-px bg-border" />
          <div className="flex-1">
            <p className="text-[11px] text-muted-foreground">90th pctl</p>
            <p className="text-sm font-semibold tabular-nums">{latency.p90Days}d</p>
          </div>
          <div className="w-px bg-border" />
          <div className="flex-1">
            <p className="text-[11px] text-muted-foreground">Previous</p>
            <p className="text-sm font-semibold tabular-nums">{latency.previousAvgDays}d</p>
          </div>
        </div>

        {/* Breakdown by type */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
            By interaction type
          </h4>
          <div className="space-y-2">
            {latency.breakdown.map((item) => {
              const pct = Math.min((item.avgDays / Math.max(latency.p90Days, 1)) * 100, 100);
              return (
                <div key={item.label} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-muted-foreground">{item.label}</span>
                    <span className="flex items-center gap-2">
                      <span className="font-medium tabular-nums">
                        {item.avgDays === 0 ? "Same day" : `${item.avgDays}d avg`}
                      </span>
                      <span className="text-muted-foreground/60 tabular-nums">
                        ({item.count})
                      </span>
                    </span>
                  </div>
                  <div className="h-1 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn(
                        "h-full rounded-full transition-all duration-500",
                        item.avgDays <= 5
                          ? "bg-emerald-500/60"
                          : item.avgDays <= 10
                            ? "bg-amber-500/60"
                            : "bg-red-500/60"
                      )}
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
