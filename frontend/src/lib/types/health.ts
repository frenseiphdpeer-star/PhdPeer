export type PhDStage =
  | "proposal"
  | "coursework"
  | "candidacy"
  | "data_collection"
  | "analysis"
  | "writing"
  | "defense_prep";

export type QuestionCategory =
  | "motivation"
  | "workload"
  | "isolation"
  | "progress_satisfaction"
  | "supervision_relationship"
  | "work_life_balance"
  | "imposter_syndrome"
  | "physical_health";

export interface HealthQuestion {
  id: string;
  text: string;
  category: QuestionCategory;
  stages: PhDStage[];
  /** 1–5 Likert scale anchors */
  lowAnchor: string;
  highAnchor: string;
}

export interface QuestionResponse {
  questionId: string;
  value: number;
}

export interface ConfidenceScore {
  overall: number;
  trend: number;
  dimensions: ConfidenceDimension[];
}

export interface ConfidenceDimension {
  label: string;
  score: number;
  category: QuestionCategory;
}

export type BurnoutLevel = "thriving" | "managing" | "strained" | "at_risk";

export interface BurnoutMetrics {
  level: BurnoutLevel;
  score: number;
  emotionalExhaustion: number;
  depersonalization: number;
  personalAccomplishment: number;
  trend: number;
}

export interface StageMessage {
  stage: PhDStage;
  stageLabel: string;
  normalizedChallenges: string[];
  encouragement: string;
  resources: StageResource[];
}

export interface StageResource {
  title: string;
  type: "article" | "exercise" | "contact" | "community";
  description: string;
}

export interface DiscussionPrompt {
  id: string;
  topic: string;
  prompt: string;
  context: string;
  category: "workload" | "progress" | "relationship" | "wellbeing" | "career";
}

export interface RiskTrajectoryPoint {
  date: string;
  risk: number;
  confidence: number;
}

export interface HealthAssessmentData {
  currentStage: PhDStage;
  questions: HealthQuestion[];
  responses: QuestionResponse[];
  confidence: ConfidenceScore;
  burnout: BurnoutMetrics;
  stageMessage: StageMessage;
  discussionPrompts: DiscussionPrompt[];
  riskTrajectory: RiskTrajectoryPoint[];
  lastAssessmentDate: string;
  isAnonymous: boolean;
}
