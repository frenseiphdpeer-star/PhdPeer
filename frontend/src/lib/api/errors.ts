import type { ApiError as ApiErrorDetail } from "@/lib/types";

/** Normalized API error for consistent handling across the app */
export interface NormalizedApiError {
  message: string;
  statusCode?: number;
  detail?: string | { msg: string }[];
}

/** Thrown by API layer with normalized error info */
export class ApiError extends Error {
  statusCode?: number;
  detail?: string | { msg: string }[];

  constructor(normalized: NormalizedApiError) {
    super(normalized.message);
    this.name = "ApiError";
    this.statusCode = normalized.statusCode;
    this.detail = normalized.detail;
    Object.setPrototypeOf(this, ApiError.prototype);
  }
}

/**
 * Normalize Axios/FastAPI error responses into a consistent shape.
 * Handles FastAPI validation errors (422), HTTP error (detail string or array).
 */
export function normalizeApiError(error: unknown): NormalizedApiError {
  if (error && typeof error === "object" && "response" in error) {
    const axiosError = error as {
      response?: {
        status?: number;
        data?: ApiErrorDetail | { detail?: string | { msg: string }[] };
      };
      message?: string;
    };

    const statusCode = axiosError.response?.status;
    const data = axiosError.response?.data;

    if (data && typeof data === "object" && "detail" in data) {
      const detail = data.detail;

      if (typeof detail === "string") {
        return {
          message: detail,
          statusCode,
          detail,
        };
      }

      if (Array.isArray(detail) && detail.length > 0) {
        const first = detail[0];
        const msg =
          typeof first === "object" && first !== null && "msg" in first
            ? String((first as { msg: string }).msg)
            : String(first);
        return {
          message: msg,
          statusCode,
          detail,
        };
      }
    }

    return {
      message: axiosError.message ?? "An unexpected error occurred",
      statusCode,
    };
  }

  if (error instanceof Error) {
    return {
      message: error.message,
    };
  }

  return {
    message: "An unexpected error occurred",
  };
}

/**
 * Normalize and throw as ApiError for typed catch handling.
 */
export function throwApiError(error: unknown): never {
  throw new ApiError(normalizeApiError(error));
}
