"use client";

import { memo, useState } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import { cn } from "@/lib/utils";

export interface ResearcherNodeData {
  label: string;
  institution: string;
  department: string;
  role: string;
  researchArea: string;
  hIndex: number;
  publications: number;
  isCurrentUser: boolean;
  institutionColor: string;
  clusterLabel: string;
  [key: string]: unknown;
}

const roleLabel: Record<string, string> = {
  phd: "PhD",
  postdoc: "Postdoc",
  faculty: "Faculty",
  industry: "Industry",
};

function ResearcherNodeComponent({ data }: NodeProps) {
  const [showTooltip, setShowTooltip] = useState(false);
  const d = data as unknown as ResearcherNodeData;
  const isMe = d.isCurrentUser;

  return (
    <div
      className="relative"
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      <Handle type="target" position={Position.Left} className="!bg-transparent !border-0 !w-0 !h-0" />

      <div
        className={cn(
          "flex items-center gap-2 rounded-lg border px-3 py-2 shadow-sm transition-shadow hover:shadow-md",
          isMe
            ? "border-primary bg-primary/10 ring-2 ring-primary/30"
            : "border-border bg-card"
        )}
      >
        {/* Institution dot */}
        <div
          className="h-3 w-3 shrink-0 rounded-full ring-1 ring-white/50"
          style={{ backgroundColor: d.institutionColor }}
        />
        <div className="min-w-0">
          <p className={cn(
            "text-xs font-medium truncate max-w-[120px]",
            isMe && "font-bold"
          )}>
            {d.label}
          </p>
          <p className="text-[9px] text-muted-foreground truncate max-w-[120px]">
            {roleLabel[d.role] ?? d.role}
          </p>
        </div>
      </div>

      {/* Hover tooltip */}
      {showTooltip && (
        <div className="absolute left-1/2 bottom-full z-50 mb-2 -translate-x-1/2 animate-in fade-in-0 zoom-in-95 duration-150">
          <div className="w-56 rounded-lg border bg-popover p-3 shadow-lg">
            <div className="flex items-center gap-2 mb-2">
              <div
                className="h-3 w-3 shrink-0 rounded-full"
                style={{ backgroundColor: d.institutionColor }}
              />
              <p className="text-xs font-semibold truncate">{d.label}</p>
            </div>
            <div className="space-y-1 text-[10px]">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Institution</span>
                <span className="font-medium text-right truncate ml-2 max-w-[120px]">{d.institution}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Department</span>
                <span className="font-medium text-right truncate ml-2 max-w-[120px]">{d.department}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Research area</span>
                <span className="font-medium text-right truncate ml-2 max-w-[120px]">{d.researchArea}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">h-index</span>
                <span className="font-medium tabular-nums">{d.hIndex}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Publications</span>
                <span className="font-medium tabular-nums">{d.publications}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Cluster</span>
                <span className="font-medium text-right truncate ml-2 max-w-[120px]">{d.clusterLabel}</span>
              </div>
            </div>
          </div>
        </div>
      )}

      <Handle type="source" position={Position.Right} className="!bg-transparent !border-0 !w-0 !h-0" />
    </div>
  );
}

export const ResearcherNode = memo(ResearcherNodeComponent);
