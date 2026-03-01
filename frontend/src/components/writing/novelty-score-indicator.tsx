"use client";

import { RadialBarChart, RadialBar, ResponsiveContainer } from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Lightbulb, TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";

interface NoveltyScoreIndicatorProps {
  score: number;
  trend: number;
  className?: string;
}

function scoreLabel(score: number) {
  if (score >= 80) return "Highly Novel";
  if (score >= 60) return "Moderately Novel";
  if (score >= 40) return "Developing";
  return "Low Novelty";
}

function scoreColor(score: number) {
  if (score >= 80) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 60) return "text-blue-600 dark:text-blue-400";
  if (score >= 40) return "text-amber-600 dark:text-amber-400";
  return "text-red-600 dark:text-red-400";
}

function fillColor(score: number) {
  if (score >= 80) return "hsl(160, 60%, 45%)";
  if (score >= 60) return "hsl(220, 70%, 50%)";
  if (score >= 40) return "hsl(40, 80%, 50%)";
  return "hsl(0, 70%, 50%)";
}

export function NoveltyScoreIndicator({ score, trend, className }: NoveltyScoreIndicatorProps) {
  const data = [
    { name: "score", value: score, fill: fillColor(score) },
  ];

  const TrendIcon = trend >= 0 ? TrendingUp : TrendingDown;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-0">
        <div className="flex items-center gap-2">
          <Lightbulb className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Novelty Score</CardTitle>
        </div>
        <p className="text-xs text-muted-foreground">
          Originality of contribution relative to literature
        </p>
      </CardHeader>
      <CardContent className="flex flex-col items-center pb-4">
        <div className="relative h-[180px] w-[180px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="70%"
              outerRadius="100%"
              startAngle={225}
              endAngle={-45}
              data={data}
              barSize={14}
            >
              <RadialBar
                dataKey="value"
                cornerRadius={8}
                background={{ fill: "hsl(var(--muted))" }}
              />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="text-3xl font-bold tabular-nums">{score}</span>
            <span className="text-xs text-muted-foreground">/100</span>
          </div>
        </div>

        <div className="mt-2 flex flex-col items-center gap-1.5">
          <span className={cn("text-sm font-semibold", scoreColor(score))}>
            {scoreLabel(score)}
          </span>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <TrendIcon className={cn(
              "h-3 w-3",
              trend >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-600 dark:text-red-400"
            )} />
            <span>
              {trend >= 0 ? "+" : ""}{trend.toFixed(1)}% from last version
            </span>
          </div>
        </div>

        <div className="mt-4 w-full space-y-2">
          {[
            { label: "Unique claims", value: 14 },
            { label: "Novel citations", value: 8 },
            { label: "Original frameworks", value: 2 },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">{item.label}</span>
              <span className="font-medium tabular-nums">{item.value}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
