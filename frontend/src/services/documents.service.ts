import { apiClient, throwApiError } from "@/lib/api";
import type { DocumentUploadResponse } from "@/lib/types";

export interface UploadDocumentParams {
  file: File;
  userId: string;
  title?: string;
  description?: string;
  documentType?: string;
  onUploadProgress?: (progress: number) => void;
}

export interface StageSuggestionResponse {
  document_id: string;
  suggested_stage: string;
  confidence_score: number;
  accepted_stage?: string;
  override_stage?: string;
  system_suggested_stage?: string;
}

/**
 * Upload a document (PDF or DOCX).
 * Returns document_id on success.
 */
export async function uploadDocument(
  params: UploadDocumentParams
): Promise<DocumentUploadResponse> {
  try {
    const formData = new FormData();
    formData.append("file", params.file);
    formData.append("user_id", params.userId);
    if (params.title != null) formData.append("title", params.title);
    if (params.description != null)
      formData.append("description", params.description);
    if (params.documentType != null)
      formData.append("document_type", params.documentType);

    const { data } = await apiClient.post<DocumentUploadResponse>(
      "/documents/upload",
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
        onUploadProgress: params.onUploadProgress
          ? (e) => {
              const pct = e.total ? Math.round((e.loaded / e.total) * 100) : 50;
              params.onUploadProgress!(pct);
            }
          : undefined,
      }
    );

    return data;
  } catch (error) {
    throwApiError(error);
  }
}

/**
 * Get stage suggestion for a document (after upload).
 */
export async function getStageSuggestion(
  documentId: string
): Promise<StageSuggestionResponse> {
  try {
    const { data } = await apiClient.get<StageSuggestionResponse>(
      `/documents/${documentId}/stage-suggestion`
    );
    return data;
  } catch (error) {
    throwApiError(error);
  }
}
