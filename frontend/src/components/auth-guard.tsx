"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore, type UserRole } from "@/lib/store/auth-store";

interface AuthGuardProps {
  children: React.ReactNode;
  allowedRoles?: UserRole[];
}

export function AuthGuard({ children, allowedRoles }: AuthGuardProps) {
  // --- AUTH TEMPORARILY BYPASSED ---
  // const router = useRouter();
  // const { isAuthenticated, user } = useAuthStore();
  //
  // useEffect(() => {
  //   if (!isAuthenticated) {
  //     router.replace("/login");
  //     return;
  //   }
  //
  //   if (allowedRoles && user && !allowedRoles.includes(user.role)) {
  //     router.replace("/dashboard");
  //   }
  // }, [isAuthenticated, user, allowedRoles, router]);
  //
  // if (!isAuthenticated) return null;
  //
  // if (allowedRoles && user && !allowedRoles.includes(user.role)) return null;

  return <>{children}</>;
}
