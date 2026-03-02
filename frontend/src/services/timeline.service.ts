import { apiClient, throwApiError } from "@/lib/api";
import type { TimelineResponse, GenerateTimelineResponse } from "@/lib/types";

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
