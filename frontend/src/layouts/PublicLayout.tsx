import { ShieldCheck } from "lucide-react";
import type { RefObject, ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

export interface PublicLayoutProps {
  mainRef: RefObject<HTMLElement | null>;
  children: ReactNode;
}

export function PublicLayout({ mainRef, children }: PublicLayoutProps) {
  const { pathname } = useLocation();
  const isLoginRoute = pathname === "/";

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-xs">
        <div
          className={cn(
            "mx-auto flex min-h-[60px] items-center justify-between gap-4",
            isLoginRoute ? "max-w-none px-6 sm:px-10 lg:px-14" : "max-w-7xl px-4 sm:px-6",
          )}
        >
          <NavLink
            to="/"
            className="inline-flex min-h-11 items-center gap-2.5 rounded-md px-1.5 text-base font-bold tracking-tight text-foreground no-underline hover:text-primary"
          >
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-xs">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <span>Examination Hub</span>
          </NavLink>

          <span className="hidden text-xs font-medium text-muted-foreground sm:inline">
            Digital Assessment Portal
          </span>
        </div>
      </header>

      <main
        id="main-content"
        ref={mainRef}
        className={cn(
          "mx-auto w-full flex-1 outline-none",
          isLoginRoute ? "max-w-none p-0" : "max-w-[1160px] px-4 py-8 sm:px-6 sm:py-10",
        )}
      >
        {children}
      </main>

      {!isLoginRoute ? (
        <footer className="border-t border-border bg-card">
          <div className="mx-auto flex max-w-[1160px] flex-col gap-2 px-4 py-4 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p>Examination Hub — Digital Assessment Platform</p>
            <p>Calm &amp; Focused Online Assessment</p>
          </div>
        </footer>
      ) : null}
    </div>
  );
}
