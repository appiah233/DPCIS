import { LogOut, Menu, ShieldCheck } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useOptionalAuth } from "@/features/auth/useAuth";
import { cn } from "@/lib/utils";

interface HeaderNavItem {
  to: string;
  label: string;
  end: boolean;
}

export interface AppHeaderProps {
  examFocusMode?: boolean;
  examTitle?: string;
  examHeaderSlot?: ReactNode;
}

export function AppHeader({
  examFocusMode = false,
  examTitle,
  examHeaderSlot,
}: AppHeaderProps) {
  const auth = useOptionalAuth();
  const { pathname } = useLocation();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  const isAuthenticated = Boolean(auth?.sessionUser && auth?.identity);
  const role = auth?.identity?.role ?? null;

  const navItems = useMemo<readonly HeaderNavItem[]>(() => {
    if (!isAuthenticated || !role) {
      return [];
    }
    if (role === "ADMIN") {
      return [
        { to: "/admin", label: "Overview", end: true },
        { to: "/admin/exams", label: "Examinations", end: true },
        { to: "/admin/results", label: "Results", end: true },
      ];
    }
    return [{ to: "/student", label: "Examinations", end: true }];
  }, [isAuthenticated, role]);

  const userLabel =
    auth?.identity?.display_name?.trim() ||
    auth?.identity?.email?.trim() ||
    "Signed in";

  const handleSignOut = async () => {
    if (!auth || isSigningOut) {
      return;
    }
    setIsDrawerOpen(false);
    setIsSigningOut(true);
    try {
      await auth.signOut();
    } finally {
      setIsSigningOut(false);
    }
  };

  if (examFocusMode) {
    return (
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-xs">
        <div className="mx-auto flex min-h-[56px] max-w-[1280px] flex-wrap items-center justify-between gap-3 px-4 py-2 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight text-foreground sm:text-base">
                {examTitle ?? "Active Examination"}
              </p>
              <p className="text-xs text-muted-foreground">Timed assessment session</p>
            </div>
          </div>

          {examHeaderSlot ? <div className="shrink-0">{examHeaderSlot}</div> : null}
        </div>
      </header>
    );
  }

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-xs">
      <div
        className={cn(
          "mx-auto flex min-h-[60px] items-center justify-between gap-3 sm:gap-4",
          pathname === "/" && !isAuthenticated
            ? "max-w-none px-6 sm:px-10 lg:px-14"
            : "max-w-7xl px-4 sm:px-6",
        )}
      >
        <div className="flex min-w-0 items-center gap-3">
          <NavLink
            to="/"
            className="inline-flex min-h-11 items-center gap-2.5 rounded-md px-1.5 text-base font-bold tracking-tight text-foreground no-underline hover:text-primary"
          >
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <span>Examination Hub</span>
          </NavLink>
        </div>

        {isAuthenticated ? (
          <>
            <nav className="hidden items-center gap-2 md:flex" aria-label="Primary">
              {navItems.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className="nav-item-link flex min-h-10 items-center rounded-md border border-transparent px-3.5 py-2 text-sm font-medium text-foreground no-underline transition-colors hover:bg-muted"
                >
                  {item.label}
                </NavLink>
              ))}

              <span
                className="ml-2 max-w-48 truncate border-l border-border pl-3.5 text-xs font-medium text-foreground"
                title={userLabel}
              >
                {userLabel}
              </span>

              <Button
                type="button"
                variant="outline"
                size="sm"
                isLoading={isSigningOut}
                onClick={() => void handleSignOut()}
              >
                <LogOut className="size-4" aria-hidden="true" />
                <span>{isSigningOut ? "Signing out..." : "Sign out"}</span>
              </Button>
            </nav>

            <div className="flex md:hidden">
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-expanded={isDrawerOpen}
                onClick={() => setIsDrawerOpen(true)}
              >
                <Menu className="size-4" aria-hidden="true" />
                <span>Menu</span>
              </Button>
            </div>

            <Dialog
              open={isDrawerOpen}
              onOpenChange={setIsDrawerOpen}
              variant="drawer"
              title="Navigation"
              description={userLabel}
            >
              <nav aria-label="Mobile navigation" className="space-y-1.5">
                {navItems.map((item, idx) => (
                  <NavLink
                    key={item.to}
                    to={item.to}
                    end={item.end}
                    data-dialog-initial-focus={idx === 0 ? "true" : undefined}
                    onClick={() => setIsDrawerOpen(false)}
                    className="nav-item-link flex min-h-11 items-center rounded-md border border-transparent px-3.5 py-2.5 text-sm font-medium text-foreground no-underline transition-colors hover:bg-muted"
                  >
                    {item.label}
                  </NavLink>
                ))}

                <div className="border-t border-border pt-4">
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full justify-start"
                    isLoading={isSigningOut}
                    onClick={() => void handleSignOut()}
                  >
                    <LogOut className="size-4" aria-hidden="true" />
                    <span>{isSigningOut ? "Signing out..." : "Sign out"}</span>
                  </Button>
                </div>
              </nav>
            </Dialog>
          </>
        ) : null}
      </div>
    </header>
  );
}
