"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { User, Building2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { SupervisionIntelligenceView } from "@/components/supervision";
import {
  researcherSupervisionDummy,
  institutionSupervisionDummy,
} from "@/lib/data/supervision-dummy";
import type { SupervisionMode } from "@/lib/types/supervision";

export default function SupervisionPage() {
  const [mode, setMode] = useState<SupervisionMode>("researcher");

  const data = mode === "researcher"
    ? researcherSupervisionDummy
    : institutionSupervisionDummy;

  return (
    <div className="mx-auto w-full max-w-[1400px] px-4 py-6 sm:px-6 lg:px-8">
      {/* Mode toggle */}
      <div className="mb-4 flex justify-end">
        <div className="inline-flex rounded-lg border bg-muted/50 p-0.5">
          <Button
            variant={mode === "researcher" ? "secondary" : "ghost"}
            size="sm"
            className={cn("h-8 gap-1.5 text-xs", mode !== "researcher" && "text-muted-foreground")}
            onClick={() => setMode("researcher")}
          >
            <User className="h-3.5 w-3.5" />
            Researcher
          </Button>
          <Button
            variant={mode === "institution" ? "secondary" : "ghost"}
            size="sm"
            className={cn("h-8 gap-1.5 text-xs", mode !== "institution" && "text-muted-foreground")}
            onClick={() => setMode("institution")}
          >
            <Building2 className="h-3.5 w-3.5" />
            Institution
          </Button>
        </div>
      </div>

      <SupervisionIntelligenceView data={data} mode={mode} />
    </div>
  );
}
