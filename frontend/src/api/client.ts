/**
 * API Client
 * 
 * Centralized HTTP client for API requests
 * - Base URL from environment variable
 * - Typed request helpers
 * - Standard error handling
 * - No business logic
 */

import {
  type ApiRequestOptions,
  type ApiResponse,
  type HttpMethod,
  type ErrorResponse,
} from './types';
import {
  ApiError,
  NetworkError,
  TimeoutError,
  createApiError,
} from './errors';

/**
 * Get base URL from environment variable
 * Falls back to default if not set
 */
function getBaseUrl(): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL;
  
  if (!baseUrl) {
    // Default to localhost backend in development
    if (import.meta.env.DEV) {
      return 'http://localhost:8000/api/v1';
    }
    throw new Error('VITE_API_BASE_URL environment variable is not set');
  }
  
  return baseUrl;
}

/**
 * Build URL with query parameters
 */
function buildUrl(endpoint: string, params?: Record<string, string | number | boolean | null | undefined>): string {
  const baseUrl = getBaseUrl();
  const url = new URL(endpoint, baseUrl);
  
  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== null && value !== undefined) {
        url.searchParams.append(key, String(value));
      }
    });
  }
  
  return url.toString();
}

/**
 * Get RBAC headers from persisted auth store (X-User-Id, X-User-Role).
 * Backend uses these for role-based access control when JWT is not present.
 */
function getRbacHeaders(): Record<string, string> {
  try {
    const raw = localStorage.getItem('frensei-auth');
    if (!raw) return {};
    const parsed = JSON.parse(raw) as { state?: { user?: { id: string; role: string } } };
    const user = parsed?.state?.user;
    if (!user?.id) return {};
    const out: Record<string, string> = {
      'X-User-Id': user.id,
    };
    if (user.role) out['X-User-Role'] = user.role;
    return out;
  } catch {
    return {};
  }
}

/**
 * Get default headers
 */
function getDefaultHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...getRbacHeaders(),
  };
  
  // Add authorization token if available
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  
  return headers;
}

/**
 * Get authentication token from storage
 * This is a placeholder - implement based on your auth strategy
 */
function getAuthToken(): string | null {
  // TODO: Implement based on your authentication strategy
  // Example: return localStorage.getItem('auth_token');
  // Example: return sessionStorage.getItem('token');
  return null;
}

/**
 * Parse error response from backend
 */
async function parseErrorResponse(response: Response): Promise<ErrorResponse> {
  try {
    const data = await response.json();
    return {
      message: data.message || data.detail || response.statusText,
      code: data.code,
      detail: data.detail,
      errors: data.errors,
      status: response.status,
    };
  } catch {
    return {
      message: response.statusText || 'An error occurred',
      status: response.status,
    };
  }
}

/**
 * Create AbortController with timeout
 */
function createTimeoutController(timeout?: number): AbortController | null {
  if (!timeout) return null;
  
  const controller = new AbortController();
  setTimeout(() => controller.abort(), timeout);
  return controller;
}

/**
 * Make HTTP request
 */
export async function request<TData = unknown>(
  method: HttpMethod,
  endpoint: string,
  options: ApiRequestOptions = {}
): Promise<ApiResponse<TData>> {
  const {
    body,
    params,
    headers = {},
    timeout,
    credentials = 'include',
    signal,
  } = options;

  // Build URL with query parameters
  const url = buildUrl(endpoint, params);
  
  // Merge headers
  const defaultHeaders = getDefaultHeaders();
  const requestHeaders = {
    ...defaultHeaders,
    ...headers,
  };
  
  // Create timeout controller if timeout is specified
  const timeoutController = createTimeoutController(timeout);
  
  // Combine abort signals if both exist
  // Note: AbortSignal.any() may not be available in all browsers
  let abortSignal: AbortSignal | undefined;
  if (signal && timeoutController?.signal) {
    // If both signals exist, create a combined controller
    // Check if AbortSignal.any is available (newer browsers)
    if (typeof AbortSignal !== 'undefined' && 'any' in AbortSignal && typeof (AbortSignal as any).any === 'function') {
      abortSignal = (AbortSignal as any).any([signal, timeoutController.signal]);
    } else {
      // Fallback: create a combined controller
      const combinedController = new AbortController();
      const abort = () => combinedController.abort();
      signal.addEventListener('abort', abort);
      timeoutController.signal.addEventListener('abort', abort);
      abortSignal = combinedController.signal;
    }
  } else {
    abortSignal = signal || timeoutController?.signal;
  }

  try {
    // Prepare request options
    const requestOptions: RequestInit = {
      method,
      headers: requestHeaders,
      credentials,
      signal: abortSignal,
    };
    
    // Add body for methods that support it
    if (body && ['POST', 'PUT', 'PATCH'].includes(method)) {
      if (body instanceof FormData) {
        // Remove Content-Type header for FormData (browser will set it with boundary)
        delete requestHeaders['Content-Type'];
        requestOptions.body = body;
      } else {
        requestOptions.body = JSON.stringify(body);
      }
    }

    // Make request
    const response = await fetch(url, requestOptions);
    
    // Handle non-OK responses
    if (!response.ok) {
      const errorResponse = await parseErrorResponse(response);
      throw createApiError(
        errorResponse.message,
        response.status,
        errorResponse
      );
    }
    
    // Parse response
    let data: TData;
    const contentType = response.headers.get('content-type');
    
    if (contentType?.includes('application/json')) {
      data = await response.json();
    } else if (contentType?.includes('text/')) {
      data = (await response.text()) as unknown as TData;
    } else {
      data = (await response.blob()) as unknown as TData;
    }
    
    return {
      data,
      status: response.status,
      statusText: response.statusText,
      headers: response.headers,
    };
  } catch (error) {
    // Handle AbortError (timeout or cancellation)
    if (error instanceof Error && error.name === 'AbortError') {
      if (timeoutController?.signal.aborted) {
        throw new TimeoutError('Request timeout');
      }
      throw new NetworkError('Request was cancelled');
    }
    
    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new NetworkError('Network error: Unable to connect to server');
    }
    
    // Re-throw ApiError instances
    if (error instanceof ApiError) {
      throw error;
    }
    
    // Wrap unknown errors
    throw new ApiError(
      error instanceof Error ? error.message : 'Unknown error occurred',
      500,
      undefined
    );
  }
}

/**
 * GET request helper
 */
export async function get<TData = unknown>(
  endpoint: string,
  options?: Omit<ApiRequestOptions, 'body'>
): Promise<ApiResponse<TData>> {
  return request<TData>('GET', endpoint, options);
}

/**
 * POST request helper
 */
export async function post<TData = unknown, TBody = unknown>(
  endpoint: string,
  body?: TBody,
  options?: Omit<ApiRequestOptions<TBody>, 'body'>
): Promise<ApiResponse<TData>> {
  return request<TData>('POST', endpoint, { ...options, body });
}

/**
 * PUT request helper
 */
export async function put<TData = unknown, TBody = unknown>(
  endpoint: string,
  body?: TBody,
  options?: Omit<ApiRequestOptions<TBody>, 'body'>
): Promise<ApiResponse<TData>> {
  return request<TData>('PUT', endpoint, { ...options, body });
}

/**
 * PATCH request helper
 */
export async function patch<TData = unknown, TBody = unknown>(
  endpoint: string,
  body?: TBody,
  options?: Omit<ApiRequestOptions<TBody>, 'body'>
): Promise<ApiResponse<TData>> {
  return request<TData>('PATCH', endpoint, { ...options, body });
}

/**
 * DELETE request helper
 */
export async function del<TData = unknown>(
  endpoint: string,
  options?: Omit<ApiRequestOptions, 'body'>
): Promise<ApiResponse<TData>> {
  return request<TData>('DELETE', endpoint, options);
}

/**
 * API Client object with all methods
 */
export const apiClient = {
  get,
  post,
  put,
  patch,
  delete: del,
  request,
};

/**
 * Set authentication token
 * This is a helper function - implement based on your auth strategy
 */
export function setAuthToken(token: string | null): void {
  // TODO: Implement based on your authentication strategy
  // Example: localStorage.setItem('auth_token', token);
  // Example: sessionStorage.setItem('token', token);
}

/**
 * Clear authentication token
 */
export function clearAuthToken(): void {
  setAuthToken(null);
}
