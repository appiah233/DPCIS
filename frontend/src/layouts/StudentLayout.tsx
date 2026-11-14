import { LogOut, Menu, ShieldCheck } from "lucide-react";
import { useState, type ReactNode, type RefObject } from "react";
import { NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { useOptionalAuth } from "@/features/auth/useAuth";
import "@/features/student/student-console.css";

export interface StudentLayoutProps {
  mainRef: RefObject<HTMLElement | null>;
  children: ReactNode;
}

export function StudentLayout({ mainRef, children }: StudentLayoutProps) {
  const auth = useOptionalAuth();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  const userLabel =
    auth?.identity?.display_name?.trim() ||
    auth?.identity?.email?.trim() ||
    "Student";

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

  return (
    <div className="student-console flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-xs">
        <div className="flex min-h-16 w-full items-center justify-between gap-4 px-5 lg:px-10">
          <div className="flex min-w-0 items-center gap-6">
            <NavLink
              to="/student"
              className="inline-flex min-h-11 items-center gap-2.5 rounded-md px-1.5 text-base font-bold tracking-tight text-foreground no-underline hover:text-primary"
            >
              <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
                <ShieldCheck className="size-4" aria-hidden="true" />
              </span>
              <span>Examination Hub</span>
            </NavLink>

            <nav aria-label="Student primary" className="hidden items-center gap-1 sm:flex">
              <NavLink
                to="/student"
                end
                className="nav-item-link inline-flex min-h-9 items-center rounded-md border border-transparent px-3 py-1.5 text-sm font-medium text-foreground no-underline transition-colors hover:bg-muted"
              >
                Examinations
              </NavLink>
            </nav>
          </div>

          <div className="hidden items-center gap-3 sm:flex">
            <div className="flex items-center gap-2 border-r border-border pr-3 text-xs">
              <span className="inline-flex size-6 items-center justify-center rounded-full bg-muted font-semibold text-foreground">
                {userLabel.charAt(0).toUpperCase()}
              </span>
              <span className="max-w-44 truncate font-medium text-foreground" title={userLabel}>
                {userLabel}
              </span>
            </div>

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
          </div>

          <div className="flex sm:hidden">
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
        </div>
      </header>

      <Dialog
        open={isDrawerOpen}
        onOpenChange={setIsDrawerOpen}
        variant="drawer"
        title="Student Menu"
        description={userLabel}
      >
        <nav aria-label="Mobile student navigation" className="space-y-2">
          <NavLink
            to="/student"
            end
            data-dialog-initial-focus="true"
            onClick={() => setIsDrawerOpen(false)}
            className="nav-item-link flex min-h-11 items-center rounded-md border border-transparent px-3.5 py-2.5 text-sm font-medium text-foreground no-underline transition-colors hover:bg-muted"
          >
            Examinations
          </NavLink>

          <div className="pt-4">
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

      <main
        id="main-content"
        ref={mainRef}
        className="w-full flex-1 px-5 py-5 outline-none lg:px-10 lg:py-8"
      >
        {children}
      </main>

      <footer className="border-t border-border bg-card">
        <div className="flex w-full flex-col gap-2 px-5 py-4 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between lg:px-10">
          <p>Examination Hub — Student Assessment Portal</p>
          <p>Progress saved automatically during your sitting</p>
        </div>
      </footer>
    </div>
  );
}
