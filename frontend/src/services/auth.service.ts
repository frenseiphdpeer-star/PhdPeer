import { apiClient } from "@/lib/api";
import type { User, UserRole } from "@/lib/store/auth-store";

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterPayload {
  email: string;
  password: string;
  full_name: string;
  role?: UserRole;
  institution?: string;
  field_of_study?: string;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  user: User;
}

export type OAuthProvider = "google" | "microsoft";

export const authService = {
  async login(credentials: LoginCredentials): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>(
      "/auth/login",
      credentials
    );
    return data;
  },

  async register(payload: RegisterPayload): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>(
      "/auth/register",
      payload
    );
    return data;
  },

  async refresh(refreshToken: string): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>("/auth/refresh", {
      refresh_token: refreshToken,
    });
    return data;
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post("/auth/logout");
    } catch {
      // Swallow – token may already be expired
    }
  },

  async me(): Promise<User> {
    const { data } = await apiClient.get<User>("/auth/me");
    return data;
  },

  getOAuthRedirectUri(provider: OAuthProvider): string {
    return `${window.location.origin}/auth/callback/${provider}`;
  },

  async getOAuthUrl(provider: OAuthProvider): Promise<string> {
    const redirectUri = this.getOAuthRedirectUri(provider);
    const { data } = await apiClient.get<{ authorization_url: string }>(
      `/auth/oauth/${provider}/url`,
      { params: { redirect_uri: redirectUri } }
    );
    return data.authorization_url;
  },

  async oauthCallback(
    provider: OAuthProvider,
    code: string
  ): Promise<AuthResponse> {
    const redirectUri = this.getOAuthRedirectUri(provider);
    const { data } = await apiClient.post<AuthResponse>(
      `/auth/oauth/${provider}/callback`,
      { code, redirect_uri: redirectUri }
    );
    return data;
  },
};
