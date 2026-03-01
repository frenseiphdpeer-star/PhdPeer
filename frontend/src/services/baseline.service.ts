import { apiClient, throwApiError } from "@/lib/api";

export interface CreateBaselineFromDocumentParams {
  documentId: string;
  programName?: string;
  institution?: string;
  fieldOfStudy?: string;
  startDate?: string;
}

export interface CreateBaselineResponse {
  baseline_id: string;
}

export async function createBaselineFromDocument(
  params: CreateBaselineFromDocumentParams
): Promise<CreateBaselineResponse> {
  try {
    const { data } = await apiClient.post<CreateBaselineResponse>(
      "/baselines/from-document",
      {
        document_id: params.documentId,
        program_name: params.programName ?? "PhD Program",
        institution: params.institution ?? "University",
        field_of_study: params.fieldOfStudy ?? "Research",
        start_date: params.startDate ?? new Date().toISOString().slice(0, 10),
      }
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}
