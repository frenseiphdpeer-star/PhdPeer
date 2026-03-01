"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CoherenceDataPoint } from "@/lib/types/writing";

interface CoherenceScoreChartProps {
  data: CoherenceDataPoint[];
  className?: string;
}

function formatMonth(dateStr: string) {
  const [y, m] = dateStr.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(m ?? "1", 10) - 1]} '${y?.slice(2)}`;
}

export function CoherenceScoreChart({ data, className }: CoherenceScoreChartProps) {
  const latest = data[data.length - 1];
  const previous = data[data.length - 2];
  const delta = latest && previous ? latest.coherence - previous.coherence : 0;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Coherence & Quality Scores</CardTitle>
          </div>
          {latest && (
            <div className="flex items-center gap-1.5">
              <span className="text-2xl font-bold tabular-nums">{latest.coherence}</span>
              <span className="text-xs text-muted-foreground">/100</span>
              {delta !== 0 && (
                <span className={cn(
                  "ml-1 text-xs font-medium",
                  delta > 0 ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-400"
                )}>
                  {delta > 0 ? "+" : ""}{delta}
                </span>
              )}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          Tracking coherence, novelty, and clarity across revisions
        </p>
      </CardHeader>
      <CardContent className="pb-4">
        <div className="h-[260px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
              <defs>
                <linearGradient id="coherenceGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-2))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--chart-2))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="noveltyGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-4))" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="hsl(var(--chart-4))" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="clarityGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="hsl(var(--chart-1))" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
              <XAxis
                dataKey="date"
                tickFormatter={formatMonth}
                tick={{ fontSize: 11 }}
                stroke="hsl(var(--muted-foreground))"
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 11 }}
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
              <Legend
                verticalAlign="top"
                height={28}
                iconSize={8}
                wrapperStyle={{ fontSize: 11 }}
              />
              <Area
                type="monotone"
                dataKey="coherence"
                stroke="hsl(var(--chart-2))"
                fill="url(#coherenceGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                name="Coherence"
              />
              <Area
                type="monotone"
                dataKey="novelty"
                stroke="hsl(var(--chart-4))"
                fill="url(#noveltyGrad)"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 4 }}
                name="Novelty"
              />
              <Area
                type="monotone"
                dataKey="clarity"
                stroke="hsl(var(--chart-1))"
                fill="url(#clarityGrad)"
                strokeWidth={1.5}
                dot={false}
                activeDot={{ r: 3 }}
                name="Clarity"
                strokeDasharray="4 2"
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </CardContent>
    </Card>
  );
}
