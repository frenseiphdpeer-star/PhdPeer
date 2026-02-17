/**
 * Role-based route guard.
 * Restricts access by role: Researcher, Supervisor, Institution Admin.
 * Segregated experience layer: each role gets its own dashboard routes.
 */

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "@/store/auth-store";
import type { Role } from "@/lib/rbac";

interface RoleGuardProps {
  children: React.ReactNode;
  /** Allowed roles; user must have one of these. */
  allowedRoles: Role[];
  /** Redirect here if role not allowed (default /home). */
  fallbackRoute?: string;
}

const DEFAULT_FALLBACK = "/home";

export function RoleGuard({
  children,
  allowedRoles,
  fallbackRoute = DEFAULT_FALLBACK,
}: RoleGuardProps) {
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    const role = user?.role ?? "researcher";
    if (!allowedRoles.includes(role)) {
      navigate(fallbackRoute, { replace: true });
    }
  }, [user?.role, allowedRoles, fallbackRoute, navigate]);

  const role = user?.role ?? "researcher";
  if (!allowedRoles.includes(role)) {
    return null;
  }
  return <>{children}</>;
}

/**
 * Researcher-only wrapper (dashboard, timeline editing).
 */
export function ResearcherOnly({
  children,
  fallbackRoute = DEFAULT_FALLBACK,
}: {
  children: React.ReactNode;
  fallbackRoute?: string;
}) {
  return (
    <RoleGuard allowedRoles={["researcher"]} fallbackRoute={fallbackRoute}>
      {children}
    </RoleGuard>
  );
}

/**
 * Supervisor-only wrapper (student risk visibility).
 */
export function SupervisorOnly({
  children,
  fallbackRoute = DEFAULT_FALLBACK,
}: {
  children: React.ReactNode;
  fallbackRoute?: string;
}) {
  return (
    <RoleGuard allowedRoles={["supervisor"]} fallbackRoute={fallbackRoute}>
      {children}
    </RoleGuard>
  );
}

/**
 * Institution Admin-only wrapper (cohort aggregation).
 */
export function AdminOnly({
  children,
  fallbackRoute = DEFAULT_FALLBACK,
}: {
  children: React.ReactNode;
  fallbackRoute?: string;
}) {
  return (
    <RoleGuard allowedRoles={["institution_admin"]} fallbackRoute={fallbackRoute}>
      {children}
    </RoleGuard>
  );
}
