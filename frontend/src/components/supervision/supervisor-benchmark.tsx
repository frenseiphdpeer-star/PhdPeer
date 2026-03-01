"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Scale } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BenchmarkData, SupervisionMode } from "@/lib/types/supervision";

interface SupervisorBenchmarkProps {
  benchmark: BenchmarkData;
  mode: SupervisionMode;
  className?: string;
}

function formatMonth(dateStr: string) {
  const [y, m] = dateStr.split("-");
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  return `${months[parseInt(m ?? "1", 10) - 1]} '${y?.slice(2)}`;
}

function percentileLabel(pct: number) {
  if (pct >= 90) return "Exceptional";
  if (pct >= 75) return "Above average";
  if (pct >= 50) return "Average";
  if (pct >= 25) return "Below average";
  return "Needs support";
}

export function SupervisorBenchmark({ benchmark, mode, className }: SupervisorBenchmarkProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Scale className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">
              {mode === "researcher" ? "Supervision Benchmark" : "Institutional Benchmark"}
            </CardTitle>
          </div>
          <Badge variant="outline" className="text-[10px]">
            {benchmark.percentileRank}th percentile
            <span className="ml-1 text-muted-foreground">·</span>
            <span className="ml-1">{percentileLabel(benchmark.percentileRank)}</span>
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "researcher"
            ? "How your supervision compares to departmental and institutional averages"
            : "Anonymized comparison of supervision quality across the institution"}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Comparison stats */}
        <div className="grid grid-cols-3 gap-3">
          {[
            {
              label: mode === "researcher" ? "Your supervisor" : "Top quartile",
              latency: benchmark.supervisorAvgLatency,
              engagement: benchmark.supervisorEngagement,
            },
            {
              label: "Department avg",
              latency: benchmark.departmentAvgLatency,
              engagement: benchmark.departmentAvgEngagement,
            },
            {
              label: "Institution avg",
              latency: benchmark.institutionAvgLatency,
              engagement: benchmark.institutionAvgEngagement,
            },
          ].map((col) => (
            <div key={col.label} className="rounded-lg bg-muted/50 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-2">
                {col.label}
              </p>
              <div className="space-y-1.5">
                <div>
                  <p className="text-lg font-bold tabular-nums">{col.latency}d</p>
                  <p className="text-[10px] text-muted-foreground">avg response</p>
                </div>
                <div>
                  <p className="text-lg font-bold tabular-nums">{col.engagement}</p>
                  <p className="text-[10px] text-muted-foreground">engagement</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Trend comparison chart */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
            Response latency trend (days)
          </h4>
          <div className="h-[200px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={benchmark.comparisonSeries}
                margin={{ top: 8, right: 8, left: -12, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="date"
                  tickFormatter={formatMonth}
                  tick={{ fontSize: 10 }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <YAxis
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
                <Legend verticalAlign="top" height={28} iconSize={8} wrapperStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="supervisor"
                  name={mode === "researcher" ? benchmark.supervisorName : "Top quartile"}
                  stroke="hsl(var(--chart-2))"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
                <Line
                  type="monotone"
                  dataKey="department"
                  name="Department"
                  stroke="hsl(var(--chart-4))"
                  strokeWidth={1.5}
                  dot={false}
                  strokeDasharray="4 2"
                />
                <Line
                  type="monotone"
                  dataKey="institution"
                  name="Institution"
                  stroke="hsl(var(--chart-5))"
                  strokeWidth={1.5}
                  dot={false}
                  strokeDasharray="6 3"
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Governance note */}
        <p className="rounded-lg border border-dashed px-3 py-2 text-[11px] text-muted-foreground leading-relaxed">
          {mode === "researcher"
            ? "Benchmarks are anonymized and aggregated. Individual supervisor data is never shared without consent."
            : "All comparisons use anonymized, aggregate data. Individual supervisor identities are protected in reporting."}
        </p>
      </CardContent>
    </Card>
  );
}
