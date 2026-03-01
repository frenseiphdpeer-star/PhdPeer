"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Flame, TrendingDown, TrendingUp, Heart } from "lucide-react";
import { cn } from "@/lib/utils";
import type { BurnoutMetrics, BurnoutLevel } from "@/lib/types/health";

interface BurnoutIndicatorProps {
  burnout: BurnoutMetrics;
  className?: string;
}

const levelConfig: Record<BurnoutLevel, {
  label: string;
  description: string;
  color: string;
  badgeVariant: "success" | "outline" | "warning" | "destructive";
  ringColor: string;
}> = {
  thriving: {
    label: "Thriving",
    description: "You're in a great place. Keep nurturing what's working.",
    color: "text-emerald-600 dark:text-emerald-400",
    badgeVariant: "success",
    ringColor: "border-emerald-500/40",
  },
  managing: {
    label: "Managing well",
    description: "You're navigating challenges with resilience. Some areas could use attention.",
    color: "text-blue-600 dark:text-blue-400",
    badgeVariant: "outline",
    ringColor: "border-blue-500/40",
  },
  strained: {
    label: "Feeling strained",
    description: "It's okay to feel this way — research can be demanding. Consider reaching out for support.",
    color: "text-amber-600 dark:text-amber-400",
    badgeVariant: "warning",
    ringColor: "border-amber-500/40",
  },
  at_risk: {
    label: "Needs support",
    description: "Your well-being is important. We encourage you to connect with support services — you don't have to manage this alone.",
    color: "text-red-500 dark:text-red-400",
    badgeVariant: "destructive",
    ringColor: "border-red-500/40",
  },
};

function DimensionGauge({ label, value, inverted = false }: { label: string; value: number; inverted?: boolean }) {
  const displayValue = inverted ? 100 - value : value;
  const color = displayValue >= 70 ? "bg-emerald-500/50" : displayValue >= 50 ? "bg-amber-500/50" : "bg-red-500/50";

  return (
    <div className="flex-1 rounded-lg bg-muted/40 p-3 text-center">
      <p className="text-[10px] font-medium text-muted-foreground mb-1">{label}</p>
      <p className="text-lg font-bold tabular-nums">{value}</p>
      <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all duration-700", color)}
          style={{ width: `${displayValue}%` }}
        />
      </div>
    </div>
  );
}

export function BurnoutIndicator({ burnout, className }: BurnoutIndicatorProps) {
  const cfg = levelConfig[burnout.level];
  const improving = burnout.trend < 0;
  const TrendIcon = improving ? TrendingDown : TrendingUp;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Heart className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Burnout Indicator</CardTitle>
          </div>
          <Badge variant={cfg.badgeVariant} className="text-[10px]">
            {cfg.label}
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Based on three research-validated dimensions
        </p>
      </CardHeader>
      <CardContent className="space-y-4 pb-5">
        {/* Central indicator */}
        <div className="flex flex-col items-center">
          <div className={cn(
            "flex h-24 w-24 items-center justify-center rounded-full border-4",
            cfg.ringColor
          )}>
            <div className="flex flex-col items-center">
              <Flame className={cn("h-5 w-5 mb-0.5", cfg.color)} />
              <span className="text-2xl font-bold tabular-nums">{burnout.score}</span>
            </div>
          </div>
          <div className="mt-2 flex items-center gap-1 text-xs text-muted-foreground">
            <TrendIcon className={cn(
              "h-3 w-3",
              improving
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-amber-600 dark:text-amber-400"
            )} />
            <span>
              {Math.abs(burnout.trend).toFixed(1)} {improving ? "lower" : "higher"} than last time
            </span>
          </div>
        </div>

        <p className="text-center text-xs text-muted-foreground leading-relaxed px-2">
          {cfg.description}
        </p>

        <Separator />

        {/* Three dimensions */}
        <div className="flex gap-2">
          <DimensionGauge label="Exhaustion" value={burnout.emotionalExhaustion} inverted />
          <DimensionGauge label="Detachment" value={burnout.depersonalization} inverted />
          <DimensionGauge label="Accomplishment" value={burnout.personalAccomplishment} />
        </div>

        <p className="text-[10px] text-muted-foreground/70 leading-relaxed text-center">
          Lower exhaustion and detachment scores with higher accomplishment indicate healthier patterns.
          This is a reflection tool — not a diagnosis.
        </p>
      </CardContent>
    </Card>
  );
}
