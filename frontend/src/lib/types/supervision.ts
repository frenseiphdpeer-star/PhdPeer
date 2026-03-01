export type SupervisionMode = "researcher" | "institution";

export type FeedbackType =
  | "meeting"
  | "written_feedback"
  | "draft_review"
  | "milestone_sign_off"
  | "ad_hoc";

export type AlertSeverity = "info" | "moderate" | "urgent";

export interface LatencyMetrics {
  currentAvgDays: number;
  previousAvgDays: number;
  trend: number;
  medianDays: number;
  p90Days: number;
  breakdown: LatencyBreakdownItem[];
}

export interface LatencyBreakdownItem {
  label: string;
  avgDays: number;
  count: number;
}

export interface FeedbackEvent {
  id: string;
  date: string;
  type: FeedbackType;
  title: string;
  summary: string;
  responseTimeDays: number;
  supervisorName: string;
  qualityRating?: number;
}

export interface EngagementMetrics {
  overallScore: number;
  trend: number;
  dimensions: EngagementDimension[];
  series: EngagementDataPoint[];
}

export interface EngagementDimension {
  label: string;
  score: number;
  description: string;
}

export interface EngagementDataPoint {
  date: string;
  score: number;
}

export interface BenchmarkData {
  supervisorName: string;
  supervisorAvgLatency: number;
  departmentAvgLatency: number;
  institutionAvgLatency: number;
  supervisorEngagement: number;
  departmentAvgEngagement: number;
  institutionAvgEngagement: number;
  percentileRank: number;
  comparisonSeries: BenchmarkSeriesPoint[];
}

export interface BenchmarkSeriesPoint {
  date: string;
  supervisor: number;
  department: number;
  institution: number;
}

export interface BottleneckAlert {
  id: string;
  severity: AlertSeverity;
  title: string;
  description: string;
  recommendation: string;
  detectedAt: string;
  category: string;
  acknowledged: boolean;
}

/** Aggregate stats shown only in institutional mode */
export interface InstitutionAggregate {
  totalResearchers: number;
  totalSupervisors: number;
  avgLatencyAcross: number;
  avgEngagementAcross: number;
  researchersAtRisk: number;
  researchersOnTrack: number;
  supervisorDistribution: SupervisorLoadItem[];
}

export interface SupervisorLoadItem {
  name: string;
  activeStudents: number;
  avgLatencyDays: number;
  engagementScore: number;
}

export interface SupervisionIntelligenceData {
  mode: SupervisionMode;
  latency: LatencyMetrics;
  feedbackEvents: FeedbackEvent[];
  engagement: EngagementMetrics;
  benchmark: BenchmarkData;
  alerts: BottleneckAlert[];
  institutionAggregate?: InstitutionAggregate;
}
