"use client";

import { useState, useMemo, useCallback } from "react";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { Sparkles, LayoutGrid, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { OpportunityCard } from "./opportunity-card";
import { OpportunityFilters } from "./opportunity-filters";
import { ApplicationTracker } from "./application-tracker";
import { OpportunityStatsBar } from "./opportunity-stats-bar";
import type {
  OpportunityDiscoveryData,
  OpportunityFilters as FiltersType,
  Opportunity,
} from "@/lib/types/opportunities";

interface OpportunityDiscoveryViewProps {
  data: OpportunityDiscoveryData;
  className?: string;
}

type ViewMode = "grid" | "list";

function filterOpportunities(opportunities: Opportunity[], filters: FiltersType): Opportunity[] {
  return opportunities.filter((op) => {
    if (filters.types.length > 0 && !filters.types.includes(op.type)) return false;
    if (filters.savedOnly && !op.isSaved) return false;
    if (filters.minMatchScore > 0 && op.matchScore < filters.minMatchScore) return false;
    if (filters.search) {
      const q = filters.search.toLowerCase();
      const haystack = [op.title, op.organization, op.description, ...op.tags]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(q)) return false;
    }
    return true;
  });
}

export function OpportunityDiscoveryView({ data, className }: OpportunityDiscoveryViewProps) {
  const [filters, setFilters] = useState<FiltersType>({
    types: [],
    search: "",
    savedOnly: false,
    minMatchScore: 0,
  });
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [opportunities, setOpportunities] = useState(data.opportunities);

  const filtered = useMemo(
    () => filterOpportunities(opportunities, filters),
    [opportunities, filters]
  );

  const sorted = useMemo(
    () => [...filtered].sort((a, b) => b.matchScore - a.matchScore),
    [filtered]
  );

  const handleToggleSave = useCallback((id: string) => {
    setOpportunities((prev) =>
      prev.map((op) =>
        op.id === id ? { ...op, isSaved: !op.isSaved } : op
      )
    );
  }, []);

  return (
    <div className={className}>
      {/* Header */}
      <div className="mb-6 flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <Sparkles className="h-5 w-5 text-primary" />
            <h2 className="text-2xl font-bold tracking-tight">Opportunity Discovery</h2>
          </div>
          <p className="mt-1 text-sm text-muted-foreground">
            AI-matched grants, conferences, and collaborations tailored to your research profile
          </p>
        </div>
        <Badge
          variant="outline"
          className="flex items-center gap-1.5 self-start border-dashed text-xs text-muted-foreground"
        >
          <Sparkles className="h-3 w-3" />
          Smart matching
        </Badge>
      </div>

      {/* Stats bar */}
      <OpportunityStatsBar stats={data.stats} className="mb-6" />

      <Separator className="mb-6" />

      {/* Main layout */}
      <div className="grid gap-6 lg:grid-cols-[1fr_340px]">
        {/* Left column — discovery feed */}
        <div className="space-y-4">
          {/* Filters + view toggle */}
          <div className="space-y-3">
            <OpportunityFilters
              filters={filters}
              onChange={setFilters}
              resultCount={sorted.length}
            />
            <div className="flex items-center justify-between">
              <p className="text-xs text-muted-foreground">
                Sorted by match score · Highest first
              </p>
              <div className="flex rounded-md border">
                <Button
                  variant={viewMode === "grid" ? "secondary" : "ghost"}
                  size="icon"
                  className="h-7 w-7 rounded-r-none"
                  onClick={() => setViewMode("grid")}
                >
                  <LayoutGrid className="h-3.5 w-3.5" />
                </Button>
                <Button
                  variant={viewMode === "list" ? "secondary" : "ghost"}
                  size="icon"
                  className="h-7 w-7 rounded-l-none"
                  onClick={() => setViewMode("list")}
                >
                  <List className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          </div>

          {/* Opportunity cards */}
          {sorted.length > 0 ? (
            <div className={cn(
              viewMode === "grid"
                ? "grid gap-4 sm:grid-cols-2"
                : "space-y-3"
            )}>
              {sorted.map((op) => (
                <OpportunityCard
                  key={op.id}
                  opportunity={op}
                  onToggleSave={handleToggleSave}
                />
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center rounded-xl border border-dashed py-16 text-center">
              <Sparkles className="mb-3 h-8 w-8 text-muted-foreground/30" />
              <p className="text-sm font-medium text-muted-foreground">No opportunities match your filters</p>
              <p className="mt-1 text-xs text-muted-foreground/70">
                Try adjusting your filters or broadening your search
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-4"
                onClick={() => setFilters({ types: [], search: "", savedOnly: false, minMatchScore: 0 })}
              >
                Clear all filters
              </Button>
            </div>
          )}
        </div>

        {/* Right column — application tracker */}
        <div className="space-y-6">
          <ApplicationTracker applications={data.applications} />
        </div>
      </div>
    </div>
  );
}
