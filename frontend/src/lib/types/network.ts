export interface ResearcherNode {
  id: string;
  name: string;
  institution: string;
  department: string;
  role: "phd" | "postdoc" | "faculty" | "industry";
  researchArea: string;
  hIndex: number;
  publications: number;
  isCurrentUser?: boolean;
  clusterId: string;
}

export interface CollaborationEdge {
  id: string;
  source: string;
  target: string;
  weight: number;
  coPublications: number;
  lastInteraction: string;
  type: "co_author" | "citation" | "committee" | "informal";
}

export interface CitationCluster {
  id: string;
  label: string;
  color: string;
  memberIds: string[];
  density: number;
  description: string;
}

export interface CollaborationMetrics {
  totalCollaborators: number;
  activeCollaborators: number;
  avgStrength: number;
  strongTies: number;
  weakTies: number;
  bridgingScore: number;
  clusteringCoefficient: number;
  reachability: number;
  strengthDistribution: StrengthBucket[];
}

export interface StrengthBucket {
  range: string;
  count: number;
}

export interface NetworkGap {
  id: string;
  type: "methodological" | "topical" | "institutional" | "interdisciplinary";
  title: string;
  description: string;
  impact: "high" | "medium" | "low";
  suggestedAction: string;
}

export interface SuggestedCollaborator {
  id: string;
  name: string;
  institution: string;
  department: string;
  role: ResearcherNode["role"];
  researchArea: string;
  matchScore: number;
  reason: string;
  sharedConnections: number;
  recentPublication?: string;
}

export interface InstitutionColor {
  institution: string;
  color: string;
}

export interface NetworkIntelligenceData {
  researchers: ResearcherNode[];
  edges: CollaborationEdge[];
  clusters: CitationCluster[];
  metrics: CollaborationMetrics;
  gaps: NetworkGap[];
  suggestedCollaborators: SuggestedCollaborator[];
  institutionColors: InstitutionColor[];
}
