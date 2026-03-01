"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

interface ResearchTimelineSkeletonProps {
  stageCount?: number;
  className?: string;
}

export function ResearchTimelineSkeleton({
  stageCount = 4,
  className,
}: ResearchTimelineSkeletonProps) {
  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <Skeleton className="mb-2 h-4 w-24" />
        <Skeleton className="h-[280px] w-full rounded-lg" />
      </div>
      <div>
        <Skeleton className="mb-3 h-4 w-20" />
        <div className="space-y-3">
          {Array.from({ length: stageCount }).map((_, i) => (
            <Card key={i}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between">
                  <Skeleton className="h-5 w-48" />
                  <div className="flex gap-2">
                    <Skeleton className="h-5 w-12" />
                    <Skeleton className="h-5 w-20" />
                  </div>
                </div>
                <div className="mt-3 space-y-2">
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-8 w-32" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}
