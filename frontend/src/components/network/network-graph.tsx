"use client";

import { useEffect, useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
  BackgroundVariant,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Network } from "lucide-react";
import { cn } from "@/lib/utils";
import { ResearcherNode, type ResearcherNodeData } from "./researcher-node";
import type {
  ResearcherNode as ResearcherData,
  CollaborationEdge,
  CitationCluster,
  InstitutionColor,
} from "@/lib/types/network";

const nodeTypes: NodeTypes = {
  researcher: ResearcherNode,
};

interface NetworkGraphProps {
  researchers: ResearcherData[];
  edges: CollaborationEdge[];
  clusters: CitationCluster[];
  institutionColors: InstitutionColor[];
  className?: string;
}

const edgeTypeStyles: Record<CollaborationEdge["type"], { color: string; animated: boolean }> = {
  co_author: { color: "hsl(var(--chart-2))", animated: false },
  citation:  { color: "hsl(var(--chart-4))", animated: true },
  committee: { color: "hsl(var(--chart-5))", animated: false },
  informal:  { color: "hsl(var(--muted-foreground))", animated: true },
};

/**
 * Cluster-based radial layout:
 * - Current user at center
 * - Each cluster forms a radial sector
 * - Nodes within a cluster are arranged in concentric arcs
 * - Deterministic and fast — O(n) layout for 1000+ nodes
 */
function computeLayout(
  researchers: ResearcherData[],
  clusters: CitationCluster[],
  institutionColors: InstitutionColor[]
): { nodes: Node[]; clusterBounds: Map<string, { cx: number; cy: number; r: number }> } {
  const colorMap = new Map(institutionColors.map((ic) => [ic.institution, ic.color]));
  const clusterMap = new Map(clusters.map((c) => [c.id, c]));

  const currentUser = researchers.find((r) => r.isCurrentUser);
  const centerX = 0;
  const centerY = 0;

  const nodes: Node[] = [];
  const clusterBounds = new Map<string, { cx: number; cy: number; r: number }>();

  if (currentUser) {
    nodes.push(makeNode(currentUser, centerX, centerY, colorMap, clusterMap));
  }

  const sectorAngle = (2 * Math.PI) / Math.max(clusters.length, 1);
  const baseRadius = 220;

  clusters.forEach((cluster, ci) => {
    const members = researchers.filter(
      (r) => r.clusterId === cluster.id && !r.isCurrentUser
    );
    const angle0 = ci * sectorAngle - Math.PI / 2;
    const clusterCx = centerX + baseRadius * Math.cos(angle0 + sectorAngle / 2);
    const clusterCy = centerY + baseRadius * Math.sin(angle0 + sectorAngle / 2);

    members.forEach((r, mi) => {
      const ring = Math.floor(mi / 4);
      const posInRing = mi % 4;
      const ringRadius = 80 + ring * 70;
      const spread = sectorAngle * 0.7;
      const memberAngle = angle0 + (sectorAngle - spread) / 2 + (posInRing / Math.max(3, Math.min(members.length - 1, 4))) * spread;
      const finalR = baseRadius + ringRadius * 0.4;

      const x = centerX + finalR * Math.cos(memberAngle);
      const y = centerY + finalR * Math.sin(memberAngle);

      nodes.push(makeNode(r, x, y, colorMap, clusterMap));
    });

    clusterBounds.set(cluster.id, {
      cx: clusterCx,
      cy: clusterCy,
      r: baseRadius * 0.6,
    });
  });

  return { nodes, clusterBounds };
}

function makeNode(
  r: ResearcherData,
  x: number,
  y: number,
  colorMap: Map<string, string>,
  clusterMap: Map<string, CitationCluster>
): Node {
  const data: ResearcherNodeData = {
    label: r.name,
    institution: r.institution,
    department: r.department,
    role: r.role,
    researchArea: r.researchArea,
    hIndex: r.hIndex,
    publications: r.publications,
    isCurrentUser: r.isCurrentUser ?? false,
    institutionColor: colorMap.get(r.institution) ?? "#6b7280",
    clusterLabel: clusterMap.get(r.clusterId)?.label ?? "",
  };

  return {
    id: r.id,
    type: "researcher",
    position: { x, y },
    data,
  };
}

function buildEdges(collabEdges: CollaborationEdge[]): Edge[] {
  return collabEdges.map((e) => {
    const style = edgeTypeStyles[e.type];
    return {
      id: e.id,
      source: e.source,
      target: e.target,
      animated: style.animated,
      style: {
        stroke: style.color,
        strokeWidth: Math.max(1, e.weight * 3),
        opacity: 0.35 + e.weight * 0.5,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 10,
        height: 10,
        color: style.color,
      },
    };
  });
}

export function NetworkGraph({
  researchers,
  edges: collabEdges,
  clusters,
  institutionColors,
  className,
}: NetworkGraphProps) {
  const { nodes: layoutNodes } = useMemo(
    () => computeLayout(researchers, clusters, institutionColors),
    [researchers, clusters, institutionColors]
  );

  const flowEdges = useMemo(() => buildEdges(collabEdges), [collabEdges]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges);

  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(flowEdges);
  }, [layoutNodes, flowEdges, setNodes, setEdges]);

  const minimapNodeColor = useCallback(
    (node: Node) => {
      const d = node.data as unknown as ResearcherNodeData;
      return d?.institutionColor ?? "#6b7280";
    },
    []
  );

  return (
    <Card className={cn("overflow-hidden", className)}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Network className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Research Network</CardTitle>
          </div>
          <div className="flex items-center gap-1.5">
            <Badge variant="outline" className="text-[10px] py-0 tabular-nums">
              {researchers.length} researchers
            </Badge>
            <Badge variant="outline" className="text-[10px] py-0 tabular-nums">
              {collabEdges.length} connections
            </Badge>
          </div>
        </div>
        <div className="flex flex-wrap gap-2 mt-1">
          {institutionColors.map((ic) => (
            <div key={ic.institution} className="flex items-center gap-1">
              <div
                className="h-2 w-2 rounded-full"
                style={{ backgroundColor: ic.color }}
              />
              <span className="text-[9px] text-muted-foreground">{ic.institution}</span>
            </div>
          ))}
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="h-[520px] w-full border-t bg-muted/10">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            nodeTypes={nodeTypes}
            fitView
            fitViewOptions={{ padding: 0.3 }}
            minZoom={0.2}
            maxZoom={2}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} className="opacity-40" />
            <Controls className="!bg-card !border !shadow-sm" />
            <MiniMap
              nodeColor={minimapNodeColor}
              className="!bg-card !border !shadow-sm"
              maskColor="rgba(0,0,0,0.08)"
            />
          </ReactFlow>
        </div>
      </CardContent>
    </Card>
  );
}
