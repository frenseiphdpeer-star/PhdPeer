/**
 * Permission hooks for RBAC.
 * Use to show/hide UI (e.g. timeline editing, risk views, cohort views).
 */

import { useAuthStore } from "@/store/auth-store";
import {
  canEditTimeline,
  canViewStudentRisk,
  canViewCohortAggregation,
  type Role,
} from "@/lib/rbac";

function useRole(): Role {
  return useAuthStore((s) => s.user?.role ?? "researcher");
}

/** Researcher only: can create/edit/commit own timeline. */
export function useCanEditTimeline(): boolean {
  return canEditTimeline(useRole());
}

/** Supervisor and Admin: can see student risk / assigned students. */
export function useCanViewStudentRisk(): boolean {
  return canViewStudentRisk(useRole());
}

/** Admin only: can see cohort aggregation (anonymized). */
export function useCanViewCohortAggregation(): boolean {
  return canViewCohortAggregation(useRole());
}

export function useRoleValue(): Role {
  return useRole();
}
