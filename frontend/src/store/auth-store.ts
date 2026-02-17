/**
 * Auth store: current user and role for RBAC.
 * Shared “event store” remains global-state; this is the segregated experience layer identity.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Role } from "@/lib/rbac";

export interface AuthUser {
  id: string;
  email: string;
  fullName: string | null;
  role: Role;
}

interface AuthState {
  user: AuthUser | null;
  isAuthenticated: boolean;
}

interface AuthActions {
  setUser: (user: AuthUser | null) => void;
  setRole: (role: Role) => void;
  logout: () => void;
}

const initialState: AuthState = {
  user: null,
  isAuthenticated: false,
};

export const useAuthStore = create<AuthState & AuthActions>()(
  persist(
    (set) => ({
      ...initialState,
      setUser: (user) =>
        set({
          user,
          isAuthenticated: user !== null,
        }),
      setRole: (role) =>
        set((state) =>
          state.user
            ? { user: { ...state.user, role } }
            : state
        ),
      logout: () => set(initialState),
    }),
    { name: "frensei-auth" }
  )
);

export function useCurrentRole(): Role {
  const user = useAuthStore((s) => s.user);
  return user?.role ?? "researcher";
}

export function useIsAuthenticated(): boolean {
  return useAuthStore((s) => s.isAuthenticated);
}
