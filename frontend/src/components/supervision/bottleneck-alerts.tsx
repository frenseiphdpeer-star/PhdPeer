"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  AlertTriangle,
  Info,
  ShieldAlert,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Lightbulb,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { BottleneckAlert, AlertSeverity, SupervisionMode } from "@/lib/types/supervision";

const severityConfig: Record<AlertSeverity, {
  icon: typeof Info;
  badgeVariant: "outline" | "warning" | "destructive";
  containerClass: string;
  label: string;
}> = {
  info: {
    icon: Info,
    badgeVariant: "outline",
    containerClass: "border-blue-500/20 bg-blue-500/5",
    label: "Informational",
  },
  moderate: {
    icon: AlertTriangle,
    badgeVariant: "warning",
    containerClass: "border-amber-500/20 bg-amber-500/5",
    label: "Moderate",
  },
  urgent: {
    icon: ShieldAlert,
    badgeVariant: "destructive",
    containerClass: "border-red-500/20 bg-red-500/5",
    label: "Requires action",
  },
};

interface BottleneckAlertsProps {
  alerts: BottleneckAlert[];
  mode: SupervisionMode;
  className?: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

function AlertItem({ alert, mode }: { alert: BottleneckAlert; mode: SupervisionMode }) {
  const [expanded, setExpanded] = useState(!alert.acknowledged);
  const cfg = severityConfig[alert.severity];
  const Icon = cfg.icon;

  return (
    <div className={cn("rounded-lg border p-3 transition-colors", cfg.containerClass)}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-3 text-left"
      >
        <Icon className="mt-0.5 h-4 w-4 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{alert.title}</span>
            <Badge variant={cfg.badgeVariant} className="text-[10px] py-0 px-1.5">
              {cfg.label}
            </Badge>
            <Badge variant="outline" className="text-[10px] py-0 px-1.5">
              {alert.category}
            </Badge>
            {alert.acknowledged && (
              <CheckCircle2 className="h-3 w-3 text-emerald-500" />
            )}
          </div>
          {!expanded && (
            <p className="mt-0.5 text-xs text-muted-foreground truncate">
              {alert.description}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-[10px] text-muted-foreground">{formatDate(alert.detectedAt)}</span>
          {expanded ? (
            <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          )}
        </div>
      </button>

      {expanded && (
        <div className="mt-3 ml-7 space-y-2">
          <p className="text-xs text-foreground/80 leading-relaxed">
            {alert.description}
          </p>
          <div className="flex items-start gap-2 rounded-md bg-background/60 px-3 py-2">
            <Lightbulb className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-500" />
            <p className="text-xs text-foreground/70 leading-relaxed">
              {alert.recommendation}
            </p>
          </div>
          {!alert.acknowledged && (
            <Button variant="outline" size="sm" className="h-7 text-xs">
              <CheckCircle2 className="mr-1.5 h-3 w-3" />
              Acknowledge
            </Button>
          )}
        </div>
      )}
    </div>
  );
}

export function BottleneckAlerts({ alerts, mode, className }: BottleneckAlertsProps) {
  const urgentCount = alerts.filter((a) => a.severity === "urgent" && !a.acknowledged).length;
  const unacknowledged = alerts.filter((a) => !a.acknowledged).length;

  const sorted = [...alerts].sort((a, b) => {
    const sevOrder: Record<AlertSeverity, number> = { urgent: 0, moderate: 1, info: 2 };
    if (a.acknowledged !== b.acknowledged) return a.acknowledged ? 1 : -1;
    return sevOrder[a.severity] - sevOrder[b.severity];
  });

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">
              {mode === "researcher" ? "Supervision Insights" : "Bottleneck Alerts"}
            </CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            {urgentCount > 0 && (
              <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                {urgentCount} urgent
              </Badge>
            )}
            {unacknowledged > 0 && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">
                {unacknowledged} new
              </Badge>
            )}
          </div>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "researcher"
            ? "Constructive observations to help optimize your supervision experience"
            : "Systemic patterns that may benefit from institutional attention"}
        </p>
      </CardHeader>
      <CardContent className="space-y-2 pb-4">
        {sorted.map((alert) => (
          <AlertItem key={alert.id} alert={alert} mode={mode} />
        ))}
        {alerts.length === 0 && (
          <div className="flex flex-col items-center py-8 text-center">
            <CheckCircle2 className="mb-2 h-8 w-8 text-emerald-500/50" />
            <p className="text-sm text-muted-foreground">
              No alerts at this time — supervision is proceeding smoothly.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
