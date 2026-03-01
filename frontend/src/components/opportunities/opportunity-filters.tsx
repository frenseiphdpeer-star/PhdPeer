"use client";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Search,
  Coins,
  Users,
  FileText,
  Presentation,
  BookmarkCheck,
  X,
  SlidersHorizontal,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { OpportunityType, OpportunityFilters as Filters } from "@/lib/types/opportunities";

interface OpportunityFiltersProps {
  filters: Filters;
  onChange: (filters: Filters) => void;
  resultCount: number;
  className?: string;
}

const typeButtons: { type: OpportunityType; label: string; icon: typeof Coins }[] = [
  { type: "grant",           label: "Grants",          icon: Coins },
  { type: "conference",      label: "Conferences",     icon: Presentation },
  { type: "call_for_papers", label: "Call for Papers",  icon: FileText },
  { type: "collaboration",   label: "Collaborations",  icon: Users },
];

export function OpportunityFilters({ filters, onChange, resultCount, className }: OpportunityFiltersProps) {
  const toggleType = (type: OpportunityType) => {
    const types = filters.types.includes(type)
      ? filters.types.filter((t) => t !== type)
      : [...filters.types, type];
    onChange({ ...filters, types });
  };

  const hasFilters = filters.types.length > 0 || filters.search || filters.savedOnly || filters.minMatchScore > 0;

  return (
    <div className={cn("space-y-3", className)}>
      {/* Search bar */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <Input
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search opportunities, organizations, tags..."
          className="pl-9 h-10"
        />
      </div>

      {/* Filter row */}
      <div className="flex flex-wrap items-center gap-2">
        <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />

        {typeButtons.map(({ type, label, icon: Icon }) => {
          const active = filters.types.includes(type);
          return (
            <Button
              key={type}
              variant={active ? "secondary" : "outline"}
              size="sm"
              className={cn(
                "h-7 gap-1.5 text-xs",
                !active && "text-muted-foreground"
              )}
              onClick={() => toggleType(type)}
            >
              <Icon className="h-3 w-3" />
              {label}
            </Button>
          );
        })}

        <div className="w-px h-5 bg-border mx-1" />

        <Button
          variant={filters.savedOnly ? "secondary" : "outline"}
          size="sm"
          className={cn(
            "h-7 gap-1.5 text-xs",
            !filters.savedOnly && "text-muted-foreground"
          )}
          onClick={() => onChange({ ...filters, savedOnly: !filters.savedOnly })}
        >
          <BookmarkCheck className="h-3 w-3" />
          Saved
        </Button>

        {/* Match score threshold */}
        <Button
          variant={filters.minMatchScore > 0 ? "secondary" : "outline"}
          size="sm"
          className={cn(
            "h-7 gap-1.5 text-xs",
            filters.minMatchScore === 0 && "text-muted-foreground"
          )}
          onClick={() =>
            onChange({ ...filters, minMatchScore: filters.minMatchScore > 0 ? 0 : 70 })
          }
        >
          70+ Match
        </Button>

        {hasFilters && (
          <>
            <div className="w-px h-5 bg-border mx-1" />
            <Button
              variant="ghost"
              size="sm"
              className="h-7 gap-1 text-xs text-muted-foreground"
              onClick={() =>
                onChange({ types: [], search: "", savedOnly: false, minMatchScore: 0 })
              }
            >
              <X className="h-3 w-3" />
              Clear
            </Button>
          </>
        )}

        <div className="flex-1" />
        <Badge variant="outline" className="text-[10px] text-muted-foreground">
          {resultCount} {resultCount === 1 ? "result" : "results"}
        </Badge>
      </div>
    </div>
  );
}
