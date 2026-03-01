"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { BarChart3, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { EngagementMetrics, SupervisionMode } from "@/lib/types/supervision";

interface EngagementQualityScoreProps {
  engagement: EngagementMetrics;
  mode: SupervisionMode;
  className?: string;
}

function scoreColor(score: number) {
  if (score >= 75) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function barColor(score: number) {
  if (score >= 75) return "bg-emerald-500/60";
  if (score >= 60) return "bg-amber-500/60";
  return "bg-red-500/60";
}

function formatMonth(dateStr: string) {
  const [y, m] = dateStr.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(m ?? "1", 10) - 1]} '${y?.slice(2)}`;
}

export function EngagementQualityScore({ engagement, mode, className }: EngagementQualityScoreProps) {
  const TrendIcon = engagement.trend >= 0 ? TrendingUp : TrendingDown;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Engagement Quality</CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            <span className={cn("text-2xl font-bold tabular-nums", scoreColor(engagement.overallScore))}>
              {engagement.overallScore}
            </span>
            <span className="text-xs text-muted-foreground">/100</span>
            <TrendIcon className={cn(
              "ml-1 h-3.5 w-3.5",
              engagement.trend >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-600 dark:text-red-400"
            )} />
            <span className={cn(
              "text-xs font-medium",
              engagement.trend >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-600 dark:text-red-400"
            )}>
              {engagement.trend >= 0 ? "+" : ""}{engagement.trend.toFixed(1)}%
            </span>
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "researcher"
            ? "Composite quality of your supervision experience"
            : "Aggregate engagement quality across the institution"}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Trend chart */}
        <div className="h-[160px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={engagement.series} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
              <defs>
                <linearGradient id="engagementGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                tickFormatter={formatMonth}
                tick={{ fontSize: 10 }}
                stroke="hsl(var(--muted-foreground))"
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 10 }}
                stroke="hsl(var(--muted-foreground))"
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: "hsl(var(--card))",
                  border: "1px solid hsl(var(--border))",
                  borderRadius: "var(--radius)",
                  fontSize: 12,
                }}
                labelFormatter={(label: unknown) =>
                  formatMonth(typeof label === "string" ? label : String(label))
                }
              />
              <Area
                type="monotone"
                dataKey="score"
                stroke="hsl(var(--chart-2))"
                fill="url(#engagementGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        <Separator />

        {/* Dimension breakdown */}
        <div>
          <h4 className="mb-3 text-xs font-medium text-muted-foreground">
            Quality dimensions
          </h4>
          <div className="space-y-3">
            {engagement.dimensions.map((dim) => (
              <div key={dim.label} className="space-y-1">
                <div className="flex items-center justify-between">
                  <div className="flex-1 min-w-0">
                    <span className="text-xs font-medium">{dim.label}</span>
                    <p className="text-[10px] text-muted-foreground/70 truncate">
                      {dim.description}
                    </p>
                  </div>
                  <span className={cn("ml-2 text-xs font-semibold tabular-nums", scoreColor(dim.score))}>
                    {dim.score}
                  </span>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-all duration-500", barColor(dim.score))}
                    style={{ width: `${dim.score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
