"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { GitCompare, Columns2, Rows2 } from "lucide-react";
import { cn } from "@/lib/utils";
import type { DiffSnapshot } from "@/lib/types/writing";

interface WritingDiffViewerProps {
  diff: DiffSnapshot;
  className?: string;
}

interface DiffLine {
  type: "added" | "removed" | "unchanged";
  content: string;
}

function computeDiff(before: string, after: string): { left: DiffLine[]; right: DiffLine[] } {
  const bLines = before.split("\n");
  const aLines = after.split("\n");

  const lcs = buildLCS(bLines, aLines);

  const left: DiffLine[] = [];
  const right: DiffLine[] = [];

  let bi = 0;
  let ai = 0;
  let li = 0;

  while (bi < bLines.length || ai < aLines.length) {
    if (li < lcs.length && bi < bLines.length && bLines[bi] === lcs[li] && ai < aLines.length && aLines[ai] === lcs[li]) {
      left.push({ type: "unchanged", content: bLines[bi]! });
      right.push({ type: "unchanged", content: aLines[ai]! });
      bi++;
      ai++;
      li++;
    } else if (bi < bLines.length && (li >= lcs.length || bLines[bi] !== lcs[li])) {
      left.push({ type: "removed", content: bLines[bi]! });
      right.push({ type: "unchanged", content: "" });
      bi++;
    } else if (ai < aLines.length && (li >= lcs.length || aLines[ai] !== lcs[li])) {
      left.push({ type: "unchanged", content: "" });
      right.push({ type: "added", content: aLines[ai]! });
      ai++;
    } else {
      break;
    }
  }

  return { left, right };
}

function buildLCS(a: string[], b: string[]): string[] {
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0) as number[]);

  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (a[i - 1] === b[j - 1]) {
        dp[i]![j] = dp[i - 1]![j - 1]! + 1;
      } else {
        dp[i]![j] = Math.max(dp[i - 1]![j]!, dp[i]![j - 1]!);
      }
    }
  }

  const result: string[] = [];
  let i = m;
  let j = n;
  while (i > 0 && j > 0) {
    if (a[i - 1] === b[j - 1]) {
      result.unshift(a[i - 1]!);
      i--;
      j--;
    } else if (dp[i - 1]![j]! > dp[i]![j - 1]!) {
      i--;
    } else {
      j--;
    }
  }

  return result;
}

const lineStyles: Record<DiffLine["type"], string> = {
  added: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border-l-2 border-emerald-500",
  removed: "bg-red-500/10 text-red-700 dark:text-red-300 border-l-2 border-red-500",
  unchanged: "text-foreground/80",
};

const linePrefix: Record<DiffLine["type"], string> = {
  added: "+",
  removed: "−",
  unchanged: " ",
};

function DiffPanel({ lines, label }: { lines: DiffLine[]; label: string }) {
  return (
    <div className="flex-1 min-w-0 overflow-hidden">
      <div className="sticky top-0 z-10 border-b bg-muted/50 px-3 py-1.5">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
      </div>
      <div className="font-mono text-[12.5px] leading-[1.7]">
        {lines.map((line, idx) => (
          <div
            key={idx}
            className={cn(
              "flex min-h-[1.7em] px-3",
              line.content === "" && line.type === "unchanged" ? "opacity-0" : lineStyles[line.type]
            )}
          >
            <span className="mr-3 w-4 shrink-0 select-none text-right text-muted-foreground/50 text-[11px]">
              {line.content !== "" ? linePrefix[line.type] : ""}
            </span>
            <span className="whitespace-pre-wrap break-words">{line.content || "\u00A0"}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function UnifiedView({ left, right }: { left: DiffLine[]; right: DiffLine[] }) {
  const merged: DiffLine[] = [];
  for (let i = 0; i < Math.max(left.length, right.length); i++) {
    const l = left[i];
    const r = right[i];
    if (l && l.type === "removed") merged.push(l);
    if (r && r.type === "added") merged.push(r);
    if (l && l.type === "unchanged" && l.content !== "") merged.push(l);
    else if (r && r.type === "unchanged" && r.content !== "" && !(l && l.type === "unchanged" && l.content !== "")) merged.push(r);
  }

  return (
    <div className="font-mono text-[12.5px] leading-[1.7]">
      {merged.map((line, idx) => (
        <div
          key={idx}
          className={cn("flex min-h-[1.7em] px-3", lineStyles[line.type])}
        >
          <span className="mr-3 w-4 shrink-0 select-none text-right text-muted-foreground/50 text-[11px]">
            {linePrefix[line.type]}
          </span>
          <span className="whitespace-pre-wrap break-words">{line.content || "\u00A0"}</span>
        </div>
      ))}
    </div>
  );
}

export function WritingDiffViewer({ diff, className }: WritingDiffViewerProps) {
  const [mode, setMode] = useState<"split" | "unified">("split");
  const { left, right } = computeDiff(diff.before, diff.after);

  const additions = right.filter((l) => l.type === "added").length;
  const deletions = left.filter((l) => l.type === "removed").length;

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <GitCompare className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Revision Diff</CardTitle>
            <Badge variant="outline" className="ml-1 font-mono text-[10px]">
              {diff.versionLabel}
            </Badge>
          </div>
          <div className="flex items-center gap-1">
            <Badge variant="success" className="text-[10px] px-1.5 py-0 font-mono">
              +{additions}
            </Badge>
            <Badge variant="destructive" className="text-[10px] px-1.5 py-0 font-mono">
              −{deletions}
            </Badge>
            <div className="ml-2 flex rounded-md border">
              <Button
                variant={mode === "split" ? "secondary" : "ghost"}
                size="icon"
                className="h-7 w-7 rounded-r-none"
                onClick={() => setMode("split")}
              >
                <Columns2 className="h-3.5 w-3.5" />
              </Button>
              <Button
                variant={mode === "unified" ? "secondary" : "ghost"}
                size="icon"
                className="h-7 w-7 rounded-l-none"
                onClick={() => setMode("unified")}
              >
                <Rows2 className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="max-h-[400px] overflow-auto rounded-b-xl border-t bg-muted/20">
          {mode === "split" ? (
            <div className="flex divide-x">
              <DiffPanel lines={left} label="Before" />
              <DiffPanel lines={right} label="After" />
            </div>
          ) : (
            <UnifiedView left={left} right={right} />
          )}
        </div>
      </CardContent>
    </Card>
  );
}
