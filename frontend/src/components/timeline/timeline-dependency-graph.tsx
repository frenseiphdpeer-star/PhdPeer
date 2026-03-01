"use client";

import { useEffect, useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { TimelineStage, TimelineMilestone } from "@/lib/types";
import { cn } from "@/lib/utils";

interface TimelineDependencyGraphProps {
  stages: TimelineStage[];
  milestones: TimelineMilestone[];
  dependencies?: Array<{ from: string; to: string }>;
  className?: string;
}

const NODE_WIDTH = 160;
const NODE_HEIGHT = 44;
const HORIZONTAL_GAP = 100;
const VERTICAL_GAP = 50;

function buildFlowNodesAndEdges(
  stages: TimelineStage[],
  milestones: TimelineMilestone[],
  dependencies?: Array<{ from: string; to: string }>
): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = [];
  const edges: Edge[] = [];
  const stageIds = new Set(stages.map((s) => s.id));
  const milestoneIds = new Set(milestones.map((m) => m.id));
  const allIds = new Set([...Array.from(stageIds), ...Array.from(milestoneIds)]);

  const getLabel = (id: string) => {
    const s = stages.find((x) => x.id === id);
    if (s) return s.title;
    const m = milestones.find((x) => x.id === id);
    if (m) return m.title;
    return id.slice(0, 8);
  };

  const getIsCritical = (id: string) =>
    milestones.find((m) => m.id === id)?.is_critical ?? false;

  if (dependencies && dependencies.length > 0) {
    const sorted = topologicalSort(dependencies.filter((d) => allIds.has(d.from) && allIds.has(d.to)));
    const layerMap = new Map<string, number>();
    sorted.forEach((id, i) => layerMap.set(id, i));

    const byLayer = new Map<number, string[]>();
    sorted.forEach((id) => {
      const layer = layerMap.get(id) ?? 0;
      if (!byLayer.has(layer)) byLayer.set(layer, []);
      byLayer.get(layer)!.push(id);
    });

    byLayer.forEach((ids, layer) => {
      ids.forEach((id, idx) => {
        const x = layer * (NODE_WIDTH + HORIZONTAL_GAP);
        const y = idx * (NODE_HEIGHT + VERTICAL_GAP);
        nodes.push({
          id,
          type: "default",
          position: { x, y },
          data: { label: getLabel(id) },
          className: cn(
            "rounded-md border px-3 py-2 text-xs font-medium",
            getIsCritical(id)
              ? "border-amber-500/60 bg-amber-50 dark:bg-amber-950/40"
              : "border-border bg-card"
          ),
        });
      });
    });

    dependencies.forEach(({ from, to }) => {
      if (allIds.has(from) && allIds.has(to)) {
        edges.push({ id: `${from}-${to}`, source: from, target: to });
      }
    });
  } else {
    stages.forEach((stage, i) => {
      const x = (i % 3) * (NODE_WIDTH + HORIZONTAL_GAP);
      const y = Math.floor(i / 3) * (NODE_HEIGHT + VERTICAL_GAP);
      nodes.push({
        id: stage.id,
        type: "default",
        position: { x, y },
        data: { label: stage.title },
        className: "rounded-md border border-border bg-card px-3 py-2 text-xs font-medium",
      });
    });
  }

  return { nodes, edges };
}

function topologicalSort(deps: Array<{ from: string; to: string }>): string[] {
  const seen = new Set<string>();
  deps.forEach(({ from, to }) => {
    seen.add(from);
    seen.add(to);
  });
  const graph = new Map<string, string[]>();
  const inDegree = new Map<string, number>();
  seen.forEach((id) => {
    graph.set(id, []);
    inDegree.set(id, 0);
  });
  deps.forEach(({ from, to }) => {
    graph.get(from)?.push(to);
    inDegree.set(to, (inDegree.get(to) ?? 0) + 1);
  });
  const queue: string[] = [];
  inDegree.forEach((deg, id) => {
    if (deg === 0) queue.push(id);
  });
  const result: string[] = [];
  while (queue.length > 0) {
    const id = queue.shift()!;
    result.push(id);
    graph.get(id)?.forEach((next) => {
      const d = (inDegree.get(next) ?? 0) - 1;
      inDegree.set(next, d);
      if (d === 0) queue.push(next);
    });
  }
  return result.length === seen.size ? result : Array.from(seen);
}

export function TimelineDependencyGraph({
  stages,
  milestones,
  dependencies,
  className,
}: TimelineDependencyGraphProps) {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(
    () => buildFlowNodesAndEdges(stages, milestones, dependencies),
    [stages, milestones, dependencies]
  );

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  if (stages.length === 0 && milestones.length === 0) return null;

  return (
    <div className={cn("h-[280px] w-full rounded-lg border bg-muted/30", className)}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.3}
        maxZoom={1.5}
      >
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
