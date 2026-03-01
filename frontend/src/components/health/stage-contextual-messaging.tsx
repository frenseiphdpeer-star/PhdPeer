"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Compass,
  BookOpen,
  Dumbbell,
  Users,
  Phone,
  ExternalLink,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { StageMessage, StageResource } from "@/lib/types/health";

interface StageContextualMessagingProps {
  stageMessage: StageMessage;
  className?: string;
}

const resourceIcons: Record<StageResource["type"], typeof BookOpen> = {
  article: BookOpen,
  exercise: Dumbbell,
  community: Users,
  contact: Phone,
};

const resourceColors: Record<StageResource["type"], string> = {
  article: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20",
  exercise: "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20",
  community: "bg-teal-500/10 text-teal-600 dark:text-teal-400 border-teal-500/20",
  contact: "bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-500/20",
};

export function StageContextualMessaging({ stageMessage, className }: StageContextualMessagingProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Compass className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Where You Are</CardTitle>
          </div>
          <Badge variant="secondary" className="text-[10px]">
            {stageMessage.stageLabel} stage
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-5 pb-5">
        {/* Encouragement */}
        <div className="rounded-xl bg-emerald-500/5 border border-emerald-500/15 p-4">
          <p className="text-sm leading-relaxed text-foreground/85">
            {stageMessage.encouragement}
          </p>
        </div>

        {/* Normalized challenges */}
        <div>
          <h4 className="mb-2.5 text-xs font-medium text-muted-foreground">
            What's normal at this stage
          </h4>
          <ul className="space-y-2">
            {stageMessage.normalizedChallenges.map((challenge, i) => (
              <li key={i} className="flex gap-2.5 text-xs leading-relaxed">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/30" />
                <span className="text-foreground/75">{challenge}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Resources */}
        <div>
          <h4 className="mb-2.5 text-xs font-medium text-muted-foreground">
            Support & resources
          </h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {stageMessage.resources.map((res) => {
              const Icon = resourceIcons[res.type];
              return (
                <button
                  key={res.title}
                  className={cn(
                    "flex items-start gap-2.5 rounded-lg border p-3 text-left transition-colors hover:bg-accent/50",
                    resourceColors[res.type]
                  )}
                >
                  <Icon className="mt-0.5 h-4 w-4 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-1">
                      <span className="text-xs font-medium">{res.title}</span>
                      <ExternalLink className="h-2.5 w-2.5 opacity-50" />
                    </div>
                    <p className="mt-0.5 text-[10px] opacity-75 leading-relaxed">
                      {res.description}
                    </p>
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
