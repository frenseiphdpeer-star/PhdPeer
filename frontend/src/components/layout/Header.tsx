"use client";

import { usePathname } from "next/navigation";
import { ThemeToggle } from "./theme-toggle";
import { UserProfileDropdown } from "./user-profile-dropdown";

const ROUTE_TITLES: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/dashboard/profile": "Profile",
  "/dashboard/settings": "Settings",
  "/dashboard/timeline": "Timeline",
  "/dashboard/writing": "Writing",
  "/dashboard/supervision": "Supervision",
  "/dashboard/health": "Wellness",
  "/dashboard/opportunities": "Opportunities",
  "/dashboard/network": "Network",
};

interface HeaderProps {
  title?: string;
}

export function Header({ title }: HeaderProps) {
  const pathname = usePathname();
  const displayTitle = title ?? ROUTE_TITLES[pathname] ?? "Dashboard";

  return (
    <header className="flex h-14 items-center justify-between border-b bg-background px-6">
      <h1 className="text-lg font-semibold">{displayTitle}</h1>
      <div className="flex items-center gap-2">
        <ThemeToggle />
        <UserProfileDropdown />
      </div>
    </header>
  );
}
