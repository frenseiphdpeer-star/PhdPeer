/**
 * Role-based access control (RBAC) — shared with backend.
 * Roles: PhD Researcher, Supervisor, Institution Admin.
 */

export type Role = "researcher" | "supervisor" | "institution_admin";

export const ROLES: Record<Role, string> = {
  researcher: "PhD Researcher",
  supervisor: "Supervisor",
  institution_admin: "Institution Admin",
};

export type Permission =
  | "timeline_edit"
  | "student_risk_visibility"
  | "cohort_aggregation";

const ROLE_PERMISSIONS: Record<Role, Set<Permission>> = {
  researcher: new Set(["timeline_edit"]),
  supervisor: new Set(["student_risk_visibility"]),
  institution_admin: new Set(["student_risk_visibility", "cohort_aggregation"]),
};

export function hasPermission(role: Role, permission: Permission): boolean {
  return ROLE_PERMISSIONS[role]?.has(permission) ?? false;
}

export function canEditTimeline(role: Role): boolean {
  return hasPermission(role, "timeline_edit");
}

export function canViewStudentRisk(role: Role): boolean {
  return hasPermission(role, "student_risk_visibility");
}

export function canViewCohortAggregation(role: Role): boolean {
  return hasPermission(role, "cohort_aggregation");
}

export function parseRole(value: string | null | undefined): Role {
  if (value === "supervisor" || value === "institution_admin" || value === "researcher") {
    return value;
  }
  return "researcher";
}
