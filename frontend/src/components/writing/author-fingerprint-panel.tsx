"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Fingerprint, Sparkles } from "lucide-react";
import { cn } from "@/lib/utils";
import type { AuthorFingerprint } from "@/lib/types/writing";

interface AuthorFingerprintPanelProps {
  fingerprint: AuthorFingerprint;
  className?: string;
}

interface MetricBarProps {
  label: string;
  value: number;
  max: number;
  unit: string;
  description?: string;
}

function MetricBar({ label, value, max, unit, description }: MetricBarProps) {
  const pct = Math.min((value / max) * 100, 100);

  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium tabular-nums">
          {typeof value === "number" && value % 1 !== 0 ? value.toFixed(1) : value}
          <span className="ml-0.5 text-muted-foreground">{unit}</span>
        </span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary/70 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>
      {description && (
        <p className="text-[10px] text-muted-foreground/70">{description}</p>
      )}
    </div>
  );
}

export function AuthorFingerprintPanel({ fingerprint, className }: AuthorFingerprintPanelProps) {
  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Fingerprint className="h-4 w-4 text-muted-foreground" />
          <CardTitle className="text-base">Author Fingerprint</CardTitle>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary" className="text-[10px]">
            {fingerprint.styleProfile}
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-4 pb-4">
        {/* Stylometric metrics */}
        <div className="space-y-3">
          <MetricBar
            label="Avg. sentence length"
            value={fingerprint.avgSentenceLength}
            max={40}
            unit=" words"
          />
          <MetricBar
            label="Vocabulary richness"
            value={Math.round(fingerprint.vocabularyRichness * 100)}
            max={100}
            unit="%"
          />
          <MetricBar
            label="Active voice ratio"
            value={Math.round(fingerprint.activeVoiceRatio * 100)}
            max={100}
            unit="%"
          />
          <MetricBar
            label="Citation density"
            value={fingerprint.citationDensity}
            max={8}
            unit="/page"
          />
          <MetricBar
            label="Hedging frequency"
            value={Math.round(fingerprint.hedgingFrequency * 100)}
            max={50}
            unit="%"
          />
          <MetricBar
            label="Readability grade"
            value={fingerprint.readabilityGrade}
            max={20}
            unit=""
            description="Flesch-Kincaid grade level"
          />
        </div>

        <Separator />

        {/* Top phrases */}
        <div>
          <h4 className="mb-2 text-xs font-medium text-muted-foreground">
            Signature Phrases
          </h4>
          <div className="flex flex-wrap gap-1.5">
            {fingerprint.topPhrases.map((p) => (
              <Badge
                key={p.phrase}
                variant="outline"
                className="text-[10px] font-normal"
              >
                &quot;{p.phrase}&quot;
                <span className="ml-1 font-mono text-muted-foreground">
                  ×{p.count}
                </span>
              </Badge>
            ))}
          </div>
        </div>

        <Separator />

        {/* AI Insights */}
        <div>
          <div className="mb-2 flex items-center gap-1.5">
            <Sparkles className="h-3 w-3 text-amber-500" />
            <h4 className="text-xs font-medium text-muted-foreground">
              Evolution Insights
            </h4>
          </div>
          <ul className="space-y-2">
            {fingerprint.insights.map((insight, idx) => (
              <li key={idx} className="flex gap-2 text-xs leading-relaxed">
                <span className="mt-0.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/50" />
                <span className="text-foreground/80">{insight}</span>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}
