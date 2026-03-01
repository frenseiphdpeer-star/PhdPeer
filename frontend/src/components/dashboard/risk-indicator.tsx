"use client";

import { AlertTriangle, CheckCircle2, Info } from "lucide-react";
import { cn } from "@/lib/utils";
import type { RiskLevel } from "@/lib/types/continuity";

interface RiskIndicatorProps {
  riskLevel: RiskLevel;
  label?: string;
  className?: string;
}

const config: Record<
  RiskLevel,
  { icon: typeof CheckCircle2; label: string; className: string }
> = {
  low: {
    icon: CheckCircle2,
    label: "On track",
    className: "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400",
  },
  medium: {
    icon: Info,
    label: "Attention needed",
    className: "border-amber-500/50 bg-amber-500/10 text-amber-700 dark:text-amber-400",
  },
  high: {
    icon: AlertTriangle,
    label: "At risk",
    className: "border-destructive/50 bg-destructive/10 text-destructive",
  },
};

export function RiskIndicator({
  riskLevel,
  label,
  className,
}: RiskIndicatorProps) {
  const { icon: Icon, label: defaultLabel, className: levelClass } = config[riskLevel];

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border px-3 py-2",
        levelClass,
        className
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      <span className="text-sm font-medium">{label ?? defaultLabel}</span>
    </div>
  );
}
