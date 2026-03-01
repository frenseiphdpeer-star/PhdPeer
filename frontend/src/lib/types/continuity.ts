/** Risk level for continuity index */
export type RiskLevel = "low" | "medium" | "high";

/** Single data point for momentum / longitudinal tracking */
export interface MomentumDataPoint {
  date: string; // ISO date
  value: number;
  label?: string;
}

/** Continuity index aggregate - backend contract */
export interface ContinuityIndexData {
  /** Overall continuity score 0-100 */
  score: number;
  riskLevel: RiskLevel;
  /** Writing velocity (words/week or similar) */
  writingVelocity: number;
  /** Milestone completion percentage 0-100 */
  milestoneCompletionPercent: number;
  /** Supervision latency in days (avg days since last meeting) */
  supervisionLatencyDays: number;
  /** Opportunity engagement score 0-100 */
  opportunityEngagementScore: number;
  /** Health trajectory -1 to 1 (declining to improving) */
  healthTrajectory: number;
  /** Momentum time series for chart (3-4 year range) */
  momentumSeries: MomentumDataPoint[];
  /** Total milestones */
  totalMilestones: number;
  /** Completed milestones */
  completedMilestones: number;
  /** Opportunities acted on / total shown */
  opportunitiesActedOn: number;
  opportunitiesTotal: number;
}
