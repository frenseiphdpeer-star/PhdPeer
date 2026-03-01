"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Gauge } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ConfidenceScore } from "@/lib/types/health";

interface ConfidenceScoreOutputProps {
  confidence: ConfidenceScore;
  className?: string;
}

function scoreColor(score: number) {
  if (score >= 70) return "text-emerald-600 dark:text-emerald-400";
  if (score >= 50) return "text-amber-600 dark:text-amber-400";
  return "text-red-500 dark:text-red-400";
}

function barFill(score: number) {
  if (score >= 70) return "bg-emerald-500/50";
  if (score >= 50) return "bg-amber-500/50";
  return "bg-red-500/50";
}

function overallLabel(score: number) {
  if (score >= 80) return "Feeling strong";
  if (score >= 65) return "Doing well";
  if (score >= 50) return "Room to grow";
  if (score >= 35) return "Some challenges";
  return "Seeking support";
}

export function ConfidenceScoreOutput({ confidence, className }: ConfidenceScoreOutputProps) {
  const TrendIcon = confidence.trend >= 0 ? TrendingUp : TrendingDown;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Gauge className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Confidence Score</CardTitle>
        </div>
        <p className="text-xs text-muted-foreground">
          A composite view of how you're feeling across key areas
        </p>
      </CardHeader>
      <CardContent className="space-y-5 pb-5">
        {/* Hero score */}
        <div className="flex flex-col items-center rounded-xl bg-muted/30 py-5">
          <span className={cn("text-5xl font-bold tabular-nums", scoreColor(confidence.overall))}>
            {confidence.overall}
          </span>
          <span className="mt-1 text-xs text-muted-foreground">/100</span>
          <span className={cn("mt-2 text-sm font-medium", scoreColor(confidence.overall))}>
            {overallLabel(confidence.overall)}
          </span>
          <div className="mt-1.5 flex items-center gap-1 text-xs text-muted-foreground">
            <TrendIcon className={cn(
              "h-3 w-3",
              confidence.trend >= 0
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-red-500 dark:text-red-400"
            )} />
            <span>
              {confidence.trend >= 0 ? "+" : ""}{confidence.trend.toFixed(1)} since last check-in
            </span>
          </div>
        </div>

        {/* Dimension breakdown */}
        <div className="space-y-3">
          {confidence.dimensions.map((dim) => (
            <div key={dim.label} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted-foreground">{dim.label}</span>
                <span className={cn("font-semibold tabular-nums", scoreColor(dim.score))}>
                  {dim.score}
                </span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full transition-all duration-700", barFill(dim.score))}
                  style={{ width: `${dim.score}%` }}
                />
              </div>
            </div>
          ))}
        </div>

        <p className="text-[10px] text-muted-foreground/70 leading-relaxed text-center">
          This score reflects your self-reported experience and is meant as a personal reflection tool,
          not a clinical assessment.
        </p>
      </CardContent>
    </Card>
  );
}
