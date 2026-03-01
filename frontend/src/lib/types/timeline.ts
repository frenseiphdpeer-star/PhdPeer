/** Timeline stage - major phase in a PhD timeline */
export interface TimelineStage {
  id: string;
  title: string;
  description: string | null;
  stage_type?: string;
  stage_order: number;
  duration_months: number | null;
  status: string;
  notes: string | null;
  /** Confidence score 0–100 for AI-generated stages */
  confidence?: number;
}

/** Timeline milestone - concrete deliverable within a stage */
export interface TimelineMilestone {
  id: string;
  title: string;
  description: string | null;
  deliverable_type: string | null;
  is_critical: boolean;
  is_completed: boolean;
  milestone_order: number;
  notes: string | null;
  /** Stage ID for grouping milestones under stages */
  stage_id?: string;
}

/** Full timeline response */
export interface TimelineResponse {
  stages: TimelineStage[];
  milestones: TimelineMilestone[];
  dependencies?: Array<{ from: string; to: string }>;
  durations?: Record<string, number>;
}
