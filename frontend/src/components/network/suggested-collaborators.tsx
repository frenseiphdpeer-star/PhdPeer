"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  UserPlus,
  Users,
  GraduationCap,
  Briefcase,
  BookOpen,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { SuggestedCollaborator } from "@/lib/types/network";

const roleConfig: Record<SuggestedCollaborator["role"], { icon: typeof GraduationCap; label: string }> = {
  phd:      { icon: GraduationCap, label: "PhD" },
  postdoc:  { icon: BookOpen,      label: "Postdoc" },
  faculty:  { icon: Briefcase,     label: "Faculty" },
  industry: { icon: Briefcase,     label: "Industry" },
};

function MatchBadge({ score }: { score: number }) {
  const color =
    score >= 80 ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/30"
    : score >= 65 ? "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/30"
    : "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/30";

  return (
    <div className={cn("flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold tabular-nums", color)}>
      {score}% match
    </div>
  );
}

interface SuggestedCollaboratorsProps {
  collaborators: SuggestedCollaborator[];
  className?: string;
}

export function SuggestedCollaborators({ collaborators, className }: SuggestedCollaboratorsProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <UserPlus className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Suggested Collaborators</CardTitle>
          </div>
          <Badge variant="outline" className="text-[10px] py-0 tabular-nums">
            {collaborators.length} suggestions
          </Badge>
        </div>
        <p className="text-xs text-muted-foreground">
          Researchers who could strengthen your network based on shared interests and gaps
        </p>
      </CardHeader>
      <CardContent className="space-y-3 pb-4">
        {collaborators.map((c) => {
          const rcfg = roleConfig[c.role];
          const RoleIcon = rcfg.icon;

          return (
            <div
              key={c.id}
              className="group rounded-lg border bg-card/50 p-3 transition-colors hover:bg-accent/30"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="flex-1 min-w-0 space-y-1.5">
                  {/* Header */}
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold">{c.name}</span>
                    <MatchBadge score={c.matchScore} />
                  </div>

                  {/* Meta */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <RoleIcon className="h-3 w-3" />
                      {rcfg.label}
                    </span>
                    <span>{c.institution}</span>
                    <span>{c.department}</span>
                  </div>

                  {/* Research area */}
                  <p className="text-[11px] text-muted-foreground">
                    Research: <span className="font-medium text-foreground/80">{c.researchArea}</span>
                  </p>

                  {/* Reason */}
                  <p className="text-[11px] text-foreground/70 leading-relaxed">
                    {c.reason}
                  </p>

                  {/* Shared + publication */}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span className="flex items-center gap-1 text-[10px] text-muted-foreground">
                      <Users className="h-3 w-3" />
                      {c.sharedConnections} shared connection{c.sharedConnections !== 1 ? "s" : ""}
                    </span>
                    {c.recentPublication && (
                      <span className="text-[10px] text-muted-foreground italic truncate max-w-[240px]">
                        Latest: {c.recentPublication}
                      </span>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex flex-col gap-1.5 shrink-0">
                  <Button size="sm" className="h-7 gap-1 text-xs">
                    <UserPlus className="h-3 w-3" />
                    Connect
                  </Button>
                  <Button variant="ghost" size="sm" className="h-7 gap-1 text-xs text-muted-foreground">
                    <ExternalLink className="h-3 w-3" />
                    Profile
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}
