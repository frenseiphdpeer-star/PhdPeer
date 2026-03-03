import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from "axios";
import { useAuthStore } from "@/lib/store/auth-store";
import { logger } from "@/lib/logger";

const log = logger.child("HTTP");

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

// ---------- request interceptor – attach Bearer token ----------
apiClient.interceptors.request.use(
  (config) => {
    const token = useAuthStore.getState().accessToken;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// ---------- retry interceptor – exponential backoff for 5xx / network errors ----------
const MAX_RETRIES = 2;
const RETRY_BASE_MS = 1000;

interface RetryMeta {
  _retryCount?: number;
  _retry?: boolean; // used by refresh logic
}

apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as InternalAxiosRequestConfig & RetryMeta;
  if (!config) return Promise.reject(error);

  const status = error.response?.status;
  const isRetryable =
    !status || status >= 500 || error.code === "ECONNABORTED";

  // Don't retry mutations by default (POST/PUT/PATCH/DELETE)
  const isSafe = config.method === "get" || config.method === "head";

  const retryCount = config._retryCount ?? 0;

  if (isRetryable && isSafe && retryCount < MAX_RETRIES) {
    config._retryCount = retryCount + 1;
    const delay = Math.min(RETRY_BASE_MS * 2 ** retryCount, 8000);
    log.warn("Retrying request", {
      url: config.url,
      attempt: config._retryCount,
      delay,
    });
    await new Promise((r) => setTimeout(r, delay));
    return apiClient(config);
  }

  return Promise.reject(error);
});

// ---------- 401 interceptor – silent token refresh ----------
let refreshPromise: Promise<string> | null = null;

apiClient.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as InternalAxiosRequestConfig & RetryMeta;
  if (!config) return Promise.reject(error);

  const isAuthRoute =
    config.url?.includes("/auth/login") ||
    config.url?.includes("/auth/register") ||
    config.url?.includes("/auth/refresh");

  if (error.response?.status !== 401 || config._retry || isAuthRoute) {
    return Promise.reject(error);
  }

  config._retry = true;

  try {
    if (!refreshPromise) refreshPromise = silentRefresh();
    const newAccessToken = await refreshPromise;
    refreshPromise = null;

    config.headers.Authorization = `Bearer ${newAccessToken}`;
    return apiClient(config);
  } catch {
    refreshPromise = null;
    // --- AUTH TEMPORARILY BYPASSED ---
    // useAuthStore.getState().clearAuth();
    // if (typeof window !== "undefined") {
    //   window.location.href = "/login";
    // }
    return Promise.reject(error);
  }
});

async function silentRefresh(): Promise<string> {
  const refreshToken = useAuthStore.getState().refreshToken;
  if (!refreshToken) throw new Error("No refresh token");

  log.info("Refreshing access token");

  const { data } = await axios.post(
    `${API_BASE_URL}/api/v1/auth/refresh`,
    { refresh_token: refreshToken },
    { headers: { "Content-Type": "application/json" } }
  );

  useAuthStore.getState().setTokens(data.access_token, data.refresh_token);
  return data.access_token;
}
