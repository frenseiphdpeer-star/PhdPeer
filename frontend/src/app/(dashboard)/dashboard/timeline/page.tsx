"use client";

import { useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { ResearchTimelineContainer } from "@/components/timeline";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Plus } from "lucide-react";

function TimelineContent() {
  const searchParams = useSearchParams();
  const [baselineId, setBaselineId] = useState<string | null>(null);
  const [inputValue, setInputValue] = useState("");

  useEffect(() => {
    const baseline = searchParams.get("baseline");
    if (baseline) {
      setBaselineId(baseline);
      setInputValue(baseline);
    }
  }, [searchParams]);

  const handleLoad = () => {
    const trimmed = inputValue.trim();
    setBaselineId(trimmed || null);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Research Timeline</h2>
          <p className="text-muted-foreground">
            PhD timeline and milestone tracking
          </p>
        </div>
        <Button asChild>
          <Link href="/dashboard/timeline/new">
            <Plus className="mr-2 h-4 w-4" />
            New timeline
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="space-y-2">
          <Label htmlFor="baseline-id">Baseline ID</Label>
          <Input
            id="baseline-id"
            placeholder="Enter baseline UUID"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleLoad()}
            className="w-72"
          />
        </div>
        <Button onClick={handleLoad}>Load timeline</Button>
      </div>

      <ResearchTimelineContainer
        baselineId={baselineId}
        showDependencyGraph
      />
    </div>
  );
}

export default function TimelinePage() {
  return (
    <Suspense fallback={<div className="space-y-6"><div className="h-8 w-48 animate-pulse rounded bg-muted" /><div className="h-64 animate-pulse rounded bg-muted" /></div>}>
      <TimelineContent />
    </Suspense>
  );
}
