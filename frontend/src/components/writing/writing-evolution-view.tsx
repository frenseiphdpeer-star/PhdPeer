"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Cpu, FileText } from "lucide-react";
import { VersionHistoryTimeline } from "./version-history-timeline";
import { CoherenceScoreChart } from "./coherence-score-chart";
import { NoveltyScoreIndicator } from "./novelty-score-indicator";
import { WritingDiffViewer } from "./writing-diff-viewer";
import { AuthorFingerprintPanel } from "./author-fingerprint-panel";
import type { WritingEvolutionData, AEIContext } from "@/lib/types/writing";

interface WritingEvolutionViewProps {
  data: WritingEvolutionData;
  className?: string;
}

/**
 * Main Writing Evolution interface.
 *
 * AEI integration surface:
 * - `aeiContext` state is prepared for Adaptive Editing Intelligence
 * - Selected version flows to all child panels
 * - `onSuggestionApply` callback ready for AEI engine connection
 */
export function WritingEvolutionView({ data, className }: WritingEvolutionViewProps) {
  const [selectedVersionId, setSelectedVersionId] = useState<string>(
    data.versions[0]?.id ?? ""
  );

  // AEI integration hook point — will be connected to the AEI engine
  const [aeiContext] = useState<AEIContext>({
    selectedVersionId,
    suggestions: [],
    onSuggestionApply: undefined,
  });

  const selectedVersion = data.versions.find((v) => v.id === selectedVersionId);

  // Suppress unused var lint while AEI is not yet wired
  void aeiContext;

  return (
    <div className={className}>
      {/* Page header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <FileText className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-bold tracking-tight">Writing Evolution</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            Track coherence, novelty, and stylistic growth across thesis revisions
          </p>
        </div>
        <Badge
          variant="outline"
          className="flex items-center gap-1.5 self-start border-dashed text-xs text-muted-foreground"
        >
          <Cpu className="h-3 w-3" />
          AEI™ Ready
        </Badge>
      </div>

      <Separator className="mb-6" />

      {/* Main grid: timeline sidebar + content area */}
      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Left column — version timeline */}
        <div className="space-y-6">
          <VersionHistoryTimeline
            versions={data.versions}
            selectedId={selectedVersionId}
            onSelect={setSelectedVersionId}
          />

          {/* Selected version stats */}
          {selectedVersion && (
            <div className="rounded-xl border bg-card p-4">
              <h4 className="mb-3 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                Selected version
              </h4>
              <div className="grid grid-cols-2 gap-3">
                {[
                  { label: "Coherence", value: `${selectedVersion.coherenceScore}/100` },
                  { label: "Novelty", value: `${selectedVersion.noveltyScore}/100` },
                  { label: "Word count", value: selectedVersion.wordCount.toLocaleString() },
                  { label: "Version", value: selectedVersion.version },
                ].map((stat) => (
                  <div key={stat.label}>
                    <p className="text-[11px] text-muted-foreground">{stat.label}</p>
                    <p className="text-sm font-semibold tabular-nums">{stat.value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right column — charts, diff, fingerprint */}
        <div className="space-y-6">
          {/* Top row: coherence chart + novelty indicator */}
          <div className="grid gap-6 xl:grid-cols-[1fr_260px]">
            <CoherenceScoreChart data={data.coherenceSeries} />
            <NoveltyScoreIndicator
              score={data.currentNoveltyScore}
              trend={data.noveltyTrend}
            />
          </div>

          {/* Diff viewer */}
          <WritingDiffViewer diff={data.diff} />

          {/* Author fingerprint */}
          <AuthorFingerprintPanel fingerprint={data.fingerprint} />
        </div>
      </div>
    </div>
  );
}
