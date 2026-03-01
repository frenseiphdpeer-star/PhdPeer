"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { MessageCircle, Copy, Check, ChevronDown, ChevronUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DiscussionPrompt } from "@/lib/types/health";

interface SupervisorDiscussionPromptsProps {
  prompts: DiscussionPrompt[];
  className?: string;
}

const categoryConfig: Record<DiscussionPrompt["category"], { label: string; color: string }> = {
  workload:     { label: "Workload",     color: "bg-amber-500/10 text-amber-700 dark:text-amber-400" },
  progress:     { label: "Progress",     color: "bg-blue-500/10 text-blue-700 dark:text-blue-400" },
  relationship: { label: "Relationship", color: "bg-purple-500/10 text-purple-700 dark:text-purple-400" },
  wellbeing:    { label: "Well-being",   color: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-400" },
  career:       { label: "Career",       color: "bg-teal-500/10 text-teal-700 dark:text-teal-400" },
};

function PromptCard({ prompt }: { prompt: DiscussionPrompt }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const cfg = categoryConfig[prompt.category];

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(prompt.prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API may not be available
    }
  };

  return (
    <div className="rounded-lg border bg-card/50 p-3 transition-colors hover:bg-accent/30">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-start gap-2.5 text-left"
      >
        <MessageCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-medium">{prompt.topic}</span>
            <Badge
              variant="outline"
              className={cn("text-[10px] py-0 px-1.5 border-0", cfg.color)}
            >
              {cfg.label}
            </Badge>
          </div>
        </div>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
        )}
      </button>

      {expanded && (
        <div className="mt-3 ml-6.5 space-y-2.5">
          {/* Suggested prompt */}
          <div className="rounded-lg bg-muted/50 p-3">
            <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground mb-1">
              Suggested conversation starter
            </p>
            <p className="text-sm text-foreground/85 leading-relaxed italic">
              &ldquo;{prompt.prompt}&rdquo;
            </p>
            <Button
              variant="ghost"
              size="sm"
              className="mt-2 h-7 gap-1.5 text-xs text-muted-foreground"
              onClick={handleCopy}
            >
              {copied ? (
                <>
                  <Check className="h-3 w-3 text-emerald-500" />
                  Copied
                </>
              ) : (
                <>
                  <Copy className="h-3 w-3" />
                  Copy to clipboard
                </>
              )}
            </Button>
          </div>

          {/* Context */}
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            {prompt.context}
          </p>
        </div>
      )}
    </div>
  );
}

export function SupervisorDiscussionPrompts({ prompts, className }: SupervisorDiscussionPromptsProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Supervisor Conversation Starters</CardTitle>
        </div>
        <p className="text-xs text-muted-foreground">
          Suggestions based on your check-in — use what feels right, skip what doesn't
        </p>
      </CardHeader>
      <CardContent className="space-y-2 pb-4">
        {prompts.map((p) => (
          <PromptCard key={p.id} prompt={p} />
        ))}
        <p className="text-[10px] text-muted-foreground/60 text-center pt-2 leading-relaxed">
          These prompts are generated from your self-reported data and are never shared with your supervisor.
          You decide what to discuss.
        </p>
      </CardContent>
    </Card>
  );
}
