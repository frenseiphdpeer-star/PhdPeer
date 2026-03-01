"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Bookmark,
  BookmarkCheck,
  ExternalLink,
  Clock,
  MapPin,
  Coins,
  Target,
  TrendingUp,
  Send,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Opportunity, OpportunityType, PhDStageRelevance, ApplicationStatus } from "@/lib/types/opportunities";

const typeConfig: Record<OpportunityType, { label: string; color: string; bg: string }> = {
  grant:           { label: "Grant",           color: "text-emerald-700 dark:text-emerald-400", bg: "bg-emerald-500/10 border-emerald-500/20" },
  conference:      { label: "Conference",      color: "text-blue-700 dark:text-blue-400",    bg: "bg-blue-500/10 border-blue-500/20" },
  call_for_papers: { label: "Call for Papers", color: "text-purple-700 dark:text-purple-400", bg: "bg-purple-500/10 border-purple-500/20" },
  collaboration:   { label: "Collaboration",   color: "text-amber-700 dark:text-amber-400",  bg: "bg-amber-500/10 border-amber-500/20" },
};

const stageShort: Record<PhDStageRelevance, string> = {
  proposal: "Proposal",
  coursework: "Coursework",
  candidacy: "Candidacy",
  data_collection: "Data Coll.",
  analysis: "Analysis",
  writing: "Writing",
  defense_prep: "Defense",
};

const statusLabel: Record<ApplicationStatus, { text: string; variant: "outline" | "secondary" | "success" | "warning" | "destructive" | "default" }> = {
  discovered:   { text: "New",         variant: "outline" },
  saved:        { text: "Saved",       variant: "secondary" },
  preparing:    { text: "Preparing",   variant: "warning" },
  submitted:    { text: "Submitted",   variant: "default" },
  under_review: { text: "Under review", variant: "default" },
  accepted:     { text: "Accepted",    variant: "success" },
  rejected:     { text: "Not selected", variant: "outline" },
  withdrawn:    { text: "Withdrawn",   variant: "outline" },
};

function MatchRing({ score }: { score: number }) {
  const radius = 22;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color =
    score >= 85 ? "stroke-emerald-500" :
    score >= 70 ? "stroke-blue-500" :
    score >= 50 ? "stroke-amber-500" :
    "stroke-red-400";

  return (
    <div className="relative flex h-14 w-14 shrink-0 items-center justify-center">
      <svg className="h-14 w-14 -rotate-90" viewBox="0 0 52 52">
        <circle cx="26" cy="26" r={radius} fill="none" className="stroke-muted" strokeWidth="3" />
        <circle
          cx="26"
          cy="26"
          r={radius}
          fill="none"
          className={color}
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <span className="absolute text-xs font-bold tabular-nums">{score}</span>
    </div>
  );
}

function LeadTimeIndicator({ days }: { days: number }) {
  const urgency =
    days <= 14 ? "text-red-600 dark:text-red-400" :
    days <= 30 ? "text-amber-600 dark:text-amber-400" :
    "text-muted-foreground";

  const label =
    days <= 7 ? "This week" :
    days <= 14 ? `${days}d — Urgent` :
    days <= 30 ? `${days}d — Soon` :
    `${days}d`;

  return (
    <div className="flex items-center gap-1 text-[11px]">
      <Clock className={cn("h-3 w-3", urgency)} />
      <span className={cn("tabular-nums font-medium", urgency)}>{label}</span>
    </div>
  );
}

function SuccessProbability({ probability }: { probability: number }) {
  const color =
    probability >= 70 ? "text-emerald-600 dark:text-emerald-400" :
    probability >= 40 ? "text-amber-600 dark:text-amber-400" :
    "text-muted-foreground";

  return (
    <div className="flex items-center gap-1 text-[11px]">
      <Target className={cn("h-3 w-3", color)} />
      <span className={cn("tabular-nums font-medium", color)}>{probability}%</span>
      <span className="text-muted-foreground">success est.</span>
    </div>
  );
}

interface OpportunityCardProps {
  opportunity: Opportunity;
  onToggleSave: (id: string) => void;
  className?: string;
}

export function OpportunityCard({ opportunity: op, onToggleSave, className }: OpportunityCardProps) {
  const tcfg = typeConfig[op.type];
  const stCfg = statusLabel[op.applicationStatus];
  const deadlineDate = new Date(op.deadline).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <Card className={cn(
      "group overflow-hidden transition-all hover:shadow-md hover:border-primary/20",
      className
    )}>
      <CardContent className="p-0">
        <div className="flex gap-4 p-4">
          {/* Match ring */}
          <MatchRing score={op.matchScore} />

          {/* Main content */}
          <div className="flex-1 min-w-0 space-y-2">
            {/* Header row */}
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold leading-snug line-clamp-1">
                  {op.title}
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">{op.organization}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                {stCfg.text !== "New" && (
                  <Badge variant={stCfg.variant} className="text-[10px] py-0 px-1.5">
                    {stCfg.text}
                  </Badge>
                )}
                <button
                  onClick={() => onToggleSave(op.id)}
                  className="rounded-md p-1 transition-colors hover:bg-accent"
                >
                  {op.isSaved ? (
                    <BookmarkCheck className="h-4 w-4 text-primary" />
                  ) : (
                    <Bookmark className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>
              </div>
            </div>

            {/* Description */}
            <p className="text-xs text-muted-foreground leading-relaxed line-clamp-2">
              {op.description}
            </p>

            {/* Meta row */}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
              <LeadTimeIndicator days={op.leadTimeDays} />
              <SuccessProbability probability={op.successProbability} />
              {op.fundingAmount && (
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                  <Coins className="h-3 w-3" />
                  <span className="font-medium">{op.fundingAmount}</span>
                </div>
              )}
              {op.location && (
                <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
                  <MapPin className="h-3 w-3" />
                  <span>{op.location}</span>
                </div>
              )}
            </div>

            {/* Tags + stage badges */}
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="outline" className={cn("text-[10px] py-0 px-1.5 border", tcfg.bg, tcfg.color)}>
                {tcfg.label}
              </Badge>
              {op.stageRelevance.slice(0, 3).map((s) => (
                <Badge key={s} variant="secondary" className="text-[10px] py-0 px-1.5 font-normal">
                  {stageShort[s]}
                </Badge>
              ))}
              {op.stageRelevance.length > 3 && (
                <span className="text-[10px] text-muted-foreground">
                  +{op.stageRelevance.length - 3} stages
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t bg-muted/20 px-4 py-2">
          <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <TrendingUp className="h-3 w-3" />
            <span>Deadline: <span className="font-medium text-foreground">{deadlineDate}</span></span>
          </div>
          <div className="flex items-center gap-1.5">
            <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs" asChild>
              <a href={op.url} target="_blank" rel="noopener noreferrer">
                Details
                <ExternalLink className="h-3 w-3" />
              </a>
            </Button>
            {(op.applicationStatus === "discovered" || op.applicationStatus === "saved") && (
              <Button size="sm" className="h-7 gap-1 text-xs">
                <Send className="h-3 w-3" />
                Apply
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
