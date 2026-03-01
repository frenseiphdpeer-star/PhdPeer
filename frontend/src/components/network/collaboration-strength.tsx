"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Link2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CollaborationMetrics } from "@/lib/types/network";

interface CollaborationStrengthProps {
  metrics: CollaborationMetrics;
  className?: string;
}

function MetricCell({ label, value, suffix }: { label: string; value: string | number; suffix?: string }) {
  return (
    <div className="flex-1 text-center">
      <p className="text-lg font-bold tabular-nums leading-none">
        {value}
        {suffix && <span className="text-xs font-normal text-muted-foreground ml-0.5">{suffix}</span>}
      </p>
      <p className="mt-1 text-[10px] text-muted-foreground">{label}</p>
    </div>
  );
}

export function CollaborationStrength({ metrics, className }: CollaborationStrengthProps) {
  const chartData = metrics.strengthDistribution.map((b) => ({
    range: b.range,
    count: b.count,
  }));

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Collaboration Strength</CardTitle>
        </div>
        <p className="text-xs text-muted-foreground">
          How strong and diverse your research connections are
        </p>
      </CardHeader>
      <CardContent className="space-y-4 pb-4">
        {/* Key metrics */}
        <div className="flex items-center rounded-lg bg-muted/40 py-3 px-2">
          <MetricCell label="Total" value={metrics.totalCollaborators} />
          <div className="w-px h-8 bg-border" />
          <MetricCell label="Active" value={metrics.activeCollaborators} />
          <div className="w-px h-8 bg-border" />
          <MetricCell label="Strong ties" value={metrics.strongTies} />
          <div className="w-px h-8 bg-border" />
          <MetricCell label="Weak ties" value={metrics.weakTies} />
        </div>

        <Separator />

        {/* Network metrics */}
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "Avg. strength", value: metrics.avgStrength.toFixed(2), desc: "Mean tie weight" },
            { label: "Bridging score", value: metrics.bridgingScore.toFixed(2), desc: "Cross-cluster links" },
            { label: "Clustering", value: metrics.clusteringCoefficient.toFixed(2), desc: "Local density" },
            { label: "Reachability", value: `${Math.round(metrics.reachability * 100)}%`, desc: "Network reach" },
          ].map((m) => (
            <div key={m.label} className="rounded-lg border bg-card/50 p-2.5">
              <p className="text-xs font-medium">{m.label}</p>
              <p className="text-lg font-bold tabular-nums">{m.value}</p>
              <p className="text-[10px] text-muted-foreground">{m.desc}</p>
            </div>
          ))}
        </div>

        <Separator />

        {/* Strength distribution chart */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
            Tie strength distribution
          </h4>
          <div className="h-[120px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                <XAxis
                  dataKey="range"
                  tick={{ fontSize: 9 }}
                  stroke="hsl(var(--muted-foreground))"
                />
                <YAxis
                  tick={{ fontSize: 9 }}
                  stroke="hsl(var(--muted-foreground))"
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)",
                    fontSize: 11,
                  }}
                />
                <Bar
                  dataKey="count"
                  fill="hsl(var(--chart-2))"
                  radius={[4, 4, 0, 0]}
                  name="Collaborators"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
