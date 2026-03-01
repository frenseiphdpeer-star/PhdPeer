export type VersionStatus = "draft" | "review" | "submitted" | "published";

export interface WritingVersion {
  id: string;
  version: string;
  date: string;
  title: string;
  wordCount: number;
  coherenceScore: number;
  noveltyScore: number;
  changesSummary: string;
  status: VersionStatus;
}

export interface CoherenceDataPoint {
  date: string;
  coherence: number;
  novelty: number;
  clarity: number;
}

export interface DiffSegment {
  type: "added" | "removed" | "unchanged";
  content: string;
}

export interface DiffSnapshot {
  before: string;
  after: string;
  versionLabel: string;
}

export interface AuthorFingerprint {
  avgSentenceLength: number;
  vocabularyRichness: number;
  activeVoiceRatio: number;
  citationDensity: number;
  hedgingFrequency: number;
  readabilityGrade: number;
  styleProfile: string;
  topPhrases: { phrase: string; count: number }[];
  insights: string[];
}

/** Hook point for future Adaptive Editing Intelligence integration */
export interface AEIContext {
  selectedVersionId: string | null;
  onSuggestionApply?: (suggestionId: string) => void;
  suggestions?: AEISuggestion[];
}

export interface AEISuggestion {
  id: string;
  type: "coherence" | "novelty" | "clarity" | "structure";
  title: string;
  description: string;
  confidence: number;
}

export interface WritingEvolutionData {
  versions: WritingVersion[];
  coherenceSeries: CoherenceDataPoint[];
  currentNoveltyScore: number;
  noveltyTrend: number;
  diff: DiffSnapshot;
  fingerprint: AuthorFingerprint;
}
