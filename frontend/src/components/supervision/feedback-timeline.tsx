"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  MessageSquare,
  Users,
  FileCheck,
  Award,
  Mail,
  Star,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { FeedbackEvent, FeedbackType, SupervisionMode } from "@/lib/types/supervision";

const typeConfig: Record<FeedbackType, { icon: typeof MessageSquare; label: string; color: string }> = {
  meeting:          { icon: Users,     label: "Meeting",        color: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30" },
  written_feedback: { icon: Mail,      label: "Written",        color: "bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/30" },
  draft_review:     { icon: FileCheck, label: "Draft Review",   color: "bg-teal-500/15 text-teal-700 dark:text-teal-400 border-teal-500/30" },
  milestone_sign_off: { icon: Award,   label: "Milestone",      color: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30" },
  ad_hoc:           { icon: MessageSquare, label: "Ad Hoc",     color: "bg-gray-500/15 text-gray-700 dark:text-gray-400 border-gray-500/30" },
};

interface FeedbackTimelineProps {
  events: FeedbackEvent[];
  mode: SupervisionMode;
  className?: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function QualityStars({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }, (_, i) => (
        <Star
          key={i}
          className={cn(
            "h-3 w-3",
            i < rating
              ? "fill-amber-400 text-amber-400"
              : "text-muted-foreground/30"
          )}
        />
      ))}
    </div>
  );
}

export function FeedbackTimeline({ events, mode, className }: FeedbackTimelineProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Feedback Timeline</CardTitle>
          </div>
          <span className="text-xs text-muted-foreground tabular-nums">
            {events.length} events
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          {mode === "researcher"
            ? "Chronological record of all supervision interactions"
            : "Recent supervision interactions across the institution"}
        </p>
      </CardHeader>
      <CardContent className="px-4 pb-4">
        <div className="max-h-[480px] overflow-y-auto pr-1">
          <div className="relative space-y-0">
            {events.map((ev, i) => {
              const cfg = typeConfig[ev.type];
              const Icon = cfg.icon;
              const isLast = i === events.length - 1;

              return (
                <div key={ev.id} className="relative flex gap-3 pb-1">
                  {/* Spine */}
                  <div className="flex flex-col items-center pt-1">
                    <div className={cn(
                      "flex h-7 w-7 shrink-0 items-center justify-center rounded-full border",
                      cfg.color
                    )}>
                      <Icon className="h-3.5 w-3.5" />
                    </div>
                    {!isLast && <div className="mt-1 h-full w-px flex-1 bg-border" />}
                  </div>

                  {/* Content */}
                  <div className="flex-1 rounded-lg border bg-card/50 p-3 mb-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline" className="text-[10px] py-0">
                        {cfg.label}
                      </Badge>
                      <span className="text-[11px] text-muted-foreground">
                        {formatDate(ev.date)}
                      </span>
                      {ev.responseTimeDays > 0 && (
                        <span className={cn(
                          "text-[11px] font-medium tabular-nums",
                          ev.responseTimeDays <= 5
                            ? "text-emerald-600 dark:text-emerald-400"
                            : ev.responseTimeDays <= 10
                              ? "text-amber-600 dark:text-amber-400"
                              : "text-red-600 dark:text-red-400"
                        )}>
                          {ev.responseTimeDays}d response
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm font-medium">{ev.title}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
                      {ev.summary}
                    </p>
                    <div className="mt-2 flex items-center justify-between">
                      <span className="text-[11px] text-muted-foreground">
                        {ev.supervisorName}
                      </span>
                      {ev.qualityRating !== undefined && (
                        <QualityStars rating={ev.qualityRating} />
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
