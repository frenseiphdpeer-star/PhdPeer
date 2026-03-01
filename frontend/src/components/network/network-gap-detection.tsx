"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  AlertTriangle,
  Lightbulb,
  Beaker,
  BookOpen,
  Building2,
  Layers,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { NetworkGap } from "@/lib/types/network";

const typeConfig: Record<NetworkGap["type"], { icon: typeof Beaker; label: string; color: string }> = {
  methodological:    { icon: Beaker,    label: "Methodological",    color: "bg-purple-500/10 text-purple-700 dark:text-purple-400 border-purple-500/20" },
  topical:           { icon: BookOpen,  label: "Topical",           color: "bg-blue-500/10 text-blue-700 dark:text-blue-400 border-blue-500/20" },
  institutional:     { icon: Building2, label: "Institutional",     color: "bg-amber-500/10 text-amber-700 dark:text-amber-400 border-amber-500/20" },
  interdisciplinary: { icon: Layers,    label: "Interdisciplinary", color: "bg-teal-500/10 text-teal-700 dark:text-teal-400 border-teal-500/20" },
};

const impactConfig: Record<NetworkGap["impact"], { label: string; variant: "destructive" | "warning" | "outline" }> = {
  high:   { label: "High impact", variant: "destructive" },
  medium: { label: "Medium",      variant: "warning" },
  low:    { label: "Low",         variant: "outline" },
};

interface NetworkGapDetectionProps {
  gaps: NetworkGap[];
  className?: string;
}

export function NetworkGapDetection({ gaps, className }: NetworkGapDetectionProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Network Gaps</CardTitle>
          </div>
          <Badge variant="outline" className="text-[10px] py-0 tabular-nums">
            {gaps.length} detected
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Structural gaps that could limit your research impact
        </p>
      </CardHeader>
      <CardContent className="space-y-3 pb-4">
        {gaps.map((gap) => {
          const tcfg = typeConfig[gap.type];
          const icfg = impactConfig[gap.impact];
          const Icon = tcfg.icon;

          return (
            <div
              key={gap.id}
              className={cn("rounded-lg border p-3", tcfg.color)}
            >
              <div className="flex items-start gap-2.5">
                <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                <div className="flex-1 min-w-0 space-y-1.5">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-xs font-medium">{gap.title}</span>
                    <Badge variant={icfg.variant} className="text-[9px] py-0 px-1.5">
                      {icfg.label}
                    </Badge>
                  </div>
                  <p className="text-[11px] text-foreground/75 leading-relaxed">
                    {gap.description}
                  </p>
                  <div className="flex items-start gap-1.5 rounded-md bg-background/50 p-2">
                    <Lightbulb className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
                    <p className="text-[10px] text-foreground/70 leading-relaxed">
                      {gap.suggestedAction}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
