"use client";

import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RiskTrajectoryPoint } from "@/lib/types/health";

interface RiskTrajectoryChartProps {
  data: RiskTrajectoryPoint[];
  className?: string;
}

function formatMonth(dateStr: string) {
  const [y, m] = dateStr.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(m ?? "1", 10) - 1]} '${y?.slice(2)}`;
}

export function RiskTrajectoryChart({ data, className }: RiskTrajectoryChartProps) {
  const latest = data[data.length - 1];
  const previous = data[data.length - 2];
  const riskDelta = latest && previous ? latest.risk - previous.risk : 0;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Well-being Trajectory</CardTitle>
          </div>
          {latest && (
            <div className="flex items-center gap-2 text-xs">
              <span className="text-muted-foreground">Current:</span>
              <span className={cn(
                "font-semibold tabular-nums",
                latest.risk <= 30
                  ? "text-emerald-600 dark:text-emerald-400"
                  : latest.risk <= 50
                    ? "text-amber-600 dark:text-amber-400"
                    : "text-red-500 dark:text-red-400"
              )}>
                {latest.risk}
              </span>
              {riskDelta !== 0 && (
                <span className={cn(
                  "tabular-nums",
                  riskDelta < 0
                    ? "text-emerald-600 dark:text-emerald-400"
                    : "text-red-500 dark:text-red-400"
                )}>
                  ({riskDelta > 0 ? "+" : ""}{riskDelta})
                </span>
              )}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Risk level and confidence over time · Lower is better
        </p>
      </CardHeader>
      <CardContent className="pb-4">
        <div className="h-[200px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="riskGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
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
              <ReferenceLine
                y={50}
                stroke="hsl(var(--muted-foreground))"
                strokeDasharray="4 4"
                strokeOpacity={0.3}
                label={{
                  value: "Attention threshold",
                  position: "insideTopRight",
                  fill: "hsl(var(--muted-foreground))",
                  fontSize: 10,
                }}
              />
              <Area
                type="monotone"
                dataKey="risk"
                stroke="hsl(var(--chart-1))"
                fill="url(#riskGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                name="Risk level"
              />
              <Line
                type="monotone"
                dataKey="confidence"
                stroke="hsl(var(--chart-2))"
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3 }}
                strokeDasharray="4 2"
                name="Confidence"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="mt-3 flex items-center justify-center gap-5 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-1.5">
            <div className="h-0.5 w-4 rounded bg-[hsl(var(--chart-1))]" />
            <span>Risk level (lower is better)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-0.5 w-4 rounded bg-[hsl(var(--chart-2))] opacity-60" style={{ backgroundImage: "repeating-linear-gradient(90deg, transparent, transparent 2px, hsl(var(--card)) 2px, hsl(var(--card)) 4px)" }} />
            <span>Confidence score</span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
