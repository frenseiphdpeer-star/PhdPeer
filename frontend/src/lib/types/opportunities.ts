export type OpportunityType = "grant" | "conference" | "call_for_papers" | "collaboration";

export type ApplicationStatus =
  | "discovered"
  | "saved"
  | "preparing"
  | "submitted"
  | "under_review"
  | "accepted"
  | "rejected"
  | "withdrawn";

export type PhDStageRelevance =
  | "proposal"
  | "coursework"
  | "candidacy"
  | "data_collection"
  | "analysis"
  | "writing"
  | "defense_prep";

export interface Opportunity {
  id: string;
  title: string;
  organization: string;
  type: OpportunityType;
  description: string;
  matchScore: number;
  successProbability: number;
  stageRelevance: PhDStageRelevance[];
  deadline: string;
  leadTimeDays: number;
  fundingAmount?: string;
  location?: string;
  url: string;
  tags: string[];
  isSaved: boolean;
  applicationStatus: ApplicationStatus;
  postedDate: string;
}

export interface ApplicationTrackerEntry {
  opportunityId: string;
  title: string;
  organization: string;
  type: OpportunityType;
  status: ApplicationStatus;
  deadline: string;
  appliedDate?: string;
  lastUpdated: string;
  matchScore: number;
}

export interface OpportunityStats {
  totalDiscovered: number;
  saved: number;
  applied: number;
  accepted: number;
  avgMatchScore: number;
}

export interface OpportunityFilters {
  types: OpportunityType[];
  search: string;
  savedOnly: boolean;
  minMatchScore: number;
}

export interface OpportunityDiscoveryData {
  opportunities: Opportunity[];
  applications: ApplicationTrackerEntry[];
  stats: OpportunityStats;
}
