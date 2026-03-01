"use client";

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FileText, GitCommit } from "lucide-react";
import type { WritingVersion, VersionStatus } from "@/lib/types/writing";

const statusConfig: Record<VersionStatus, { label: string; variant: "default" | "secondary" | "success" | "warning" | "outline" }> = {
  draft:     { label: "Draft",     variant: "outline" },
  review:    { label: "In Review", variant: "warning" },
  submitted: { label: "Submitted", variant: "secondary" },
  published: { label: "Published", variant: "success" },
};

interface VersionHistoryTimelineProps {
  versions: WritingVersion[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  className?: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function VersionHistoryTimeline({
  versions,
  selectedId,
  onSelect,
  className,
}: VersionHistoryTimelineProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <GitCommit className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Version History</CardTitle>
        </div>
        <p className="text-xs text-muted-foreground">
          {versions.length} versions · Click to inspect
        </p>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <div className="relative space-y-0">
          {versions.map((v, i) => {
            const isSelected = v.id === selectedId;
            const isLast = i === versions.length - 1;
            const cfg = statusConfig[v.status];

            return (
              <button
                key={v.id}
                onClick={() => onSelect(v.id)}
                className={cn(
                  "relative flex w-full gap-3 rounded-lg p-3 text-left transition-colors",
                  isSelected
                    ? "bg-accent"
                    : "hover:bg-accent/50"
                )}
              >
                {/* Timeline spine */}
                <div className="flex flex-col items-center pt-0.5">
                  <div
                    className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-2 transition-colors",
                      isSelected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-muted-foreground/30 bg-background text-muted-foreground"
                    )}
                  >
                    <FileText className="h-3.5 w-3.5" />
                  </div>
                  {!isLast && (
                    <div className="mt-1 h-full w-px flex-1 bg-border" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 space-y-1 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-semibold text-muted-foreground">
                      {v.version}
                    </span>
                    <Badge variant={cfg.variant} className="text-[10px] px-1.5 py-0">
                      {cfg.label}
                    </Badge>
                  </div>
                  <p className="text-sm font-medium leading-snug">{v.title}</p>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {v.changesSummary}
                  </p>
                  <div className="flex items-center gap-3 text-[11px] text-muted-foreground">
                    <span>{formatDate(v.date)}</span>
                    <span>·</span>
                    <span>{v.wordCount.toLocaleString()} words</span>
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
