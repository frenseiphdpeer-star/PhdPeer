/**
 * Timeline types – mirrors the OpenAPI schema from
 * backend/app/schemas/timeline.py.
 *
 * Keep in sync: any change to the Pydantic models must be reflected here.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type StageType =
  | "literature_review"
  | "methodology"
  | "data_collection"
  | "analysis"
  | "writing"
  | "defense_preparation"
  | "revision"
  | "publication"
  | "coursework"
  | "fieldwork"
  | "other";

export type StageStatus =
  | "not_started"
  | "in_progress"
  | "completed"
  | "delayed";

export type DeliverableType =
  | "paper"
  | "presentation"
  | "dataset"
  | "code"
  | "thesis_chapter"
  | "proposal"
  | "review"
  | "report"
  | "defense"
  | "other";

export type MilestoneState =
  | "upcoming"
  | "active"
  | "completed"
  | "delayed";

export type SuggestionStatus = "pending" | "accepted" | "rejected";

export type SuggestionReason =
  | "milestone_delay"
  | "supervision_inactivity"
  | "writing_stagnation";

// ---------------------------------------------------------------------------
// Core domain objects
// ---------------------------------------------------------------------------

/** A major phase in a PhD timeline. */
export interface TimelineStage {
  id: string;
  title: string;
  description: string | null;
  stage_type: StageType | null;
  stage_order: number;
  start_date: string | null;
  end_date: string | null;
  duration_months: number | null;
  status: StageStatus;
  notes: string | null;
  /** AI confidence score 0–100. */
  confidence: number | null;
}

/** A concrete deliverable / checkpoint within a stage. */
export interface TimelineMilestone {
  id: string;
  title: string;
  description: string | null;
  deliverable_type: DeliverableType | null;
  is_critical: boolean;
  is_completed: boolean;
  milestone_order: number;
  target_date: string | null;
  actual_completion_date: string | null;
  state: MilestoneState;
  notes: string | null;
  /** Parent stage ID. */
  stage_id: string;
}

/** Directed dependency edge between stages / milestones. */
export interface Dependency {
  from: string;
  to: string;
}

/** Per-stage duration estimate. */
export interface DurationEstimate {
  stage_id: string;
  estimated_months: number | null;
  start_date: string | null;
  end_date: string | null;
}

// ---------------------------------------------------------------------------
// API response contracts
// ---------------------------------------------------------------------------

/** Full timeline payload – the canonical response. */
export interface TimelineResponse {
  timeline_id: string;
  baseline_id: string;
  title: string;
  description: string | null;
  stages: TimelineStage[];
  milestones: TimelineMilestone[];
  dependencies: Dependency[];
  durations: DurationEstimate[];
  created_at: string | null;
  updated_at: string | null;
}

/** Response after generating a draft timeline. */
export interface GenerateTimelineResponse {
  timeline_id: string;
  baseline_id: string;
  draft_timeline_id: string;
}

/** A timeline adjustment suggestion. */
export interface TimelineSuggestion {
  id: string;
  committed_timeline_id: string;
  reason: SuggestionReason;
  title: string;
  message: string;
  suggestion_payload: Record<string, unknown>;
  status: SuggestionStatus;
  responded_at: string | null;
}
