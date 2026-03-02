import { apiClient, throwApiError } from "@/lib/api";
import type {
  TimelineResponse,
  GenerateTimelineResponse,
  TimelineStage,
  TimelineMilestone,
} from "@/lib/types";

export interface GenerateTimelineParams {
  baselineId: string;
  title?: string;
}

export async function generateTimeline(
  params: GenerateTimelineParams
): Promise<GenerateTimelineResponse> {
  try {
    const { data } = await apiClient.post<GenerateTimelineResponse>(
      "/timeline/generate",
      {
        baseline_id: params.baselineId,
        title: params.title,
      }
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}

export async function getTimeline(
  baselineId: string
): Promise<TimelineResponse> {
  try {
    const { data } = await apiClient.get<TimelineResponse>(
      `/timeline/${baselineId}`
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}

export async function getTimelineStages(
  baselineId: string
): Promise<TimelineStage[]> {
  try {
    const { data } = await apiClient.get<TimelineStage[]>(
      `/timeline/${baselineId}/stages`
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}

export async function getTimelineMilestones(
  baselineId: string
): Promise<TimelineMilestone[]> {
  try {
    const { data } = await apiClient.get<TimelineMilestone[]>(
      `/timeline/${baselineId}/milestones`
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}
