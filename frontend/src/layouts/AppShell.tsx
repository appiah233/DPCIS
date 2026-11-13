import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { AppHeader } from "@/components/AppHeader";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { cn } from "@/lib/utils";

interface RouteMetadata {
  title: string;
  announcement: string;
  examFocusMode?: boolean;
}

function resolveRouteMetadata(pathname: string): RouteMetadata {
  if (pathname === "/") {
    return {
      title: "Sign In | Examination Hub",
      announcement: "Sign in page",
    };
  }
  if (pathname === "/student") {
    return {
      title: "Examinations | Examination Hub",
      announcement: "Examinations page",
    };
  }
  if (pathname.startsWith("/student/attempts/")) {
    return {
      title: "Active Examination | Examination Hub",
      announcement: "Active timed examination page",
      examFocusMode: true,
    };
  }
  if (pathname.startsWith("/student/results/")) {
    return {
      title: "Examination Result | Examination Hub",
      announcement: "Examination result page",
    };
  }
  if (pathname.startsWith("/student/exams/")) {
    return {
      title: "Exam Instructions | Examination Hub",
      announcement: "Examination instructions page",
    };
  }
  if (pathname === "/admin") {
    return {
      title: "Examinations | Examination Hub",
      announcement: "Examinations management page",
    };
  }
  if (pathname === "/admin/exams/new") {
    return {
      title: "Create Examination | Examination Hub",
      announcement: "Create examination page",
    };
  }
  if (/^\/admin\/exams\/[^/]+\/results\/?$/.test(pathname)) {
    return {
      title: "Examination Results | Examination Hub",
      announcement: "Examination results page",
    };
  }
  if (pathname.startsWith("/admin/exams/")) {
    return {
      title: "Manage Examination | Examination Hub",
      announcement: "Manage examination page",
    };
  }
  return {
    title: "Page Not Found | Examination Hub",
    announcement: "Page not found",
  };
}

export interface AppShellProps {
  examFocusMode?: boolean;
  examTitle?: string;
  examHeaderSlot?: ReactNode;
}

export function AppShell({
  examFocusMode: examFocusModeOverride,
  examTitle,
  examHeaderSlot,
}: AppShellProps) {
  const { pathname } = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const isFirstRenderRef = useRef(true);
  const [routeAnnouncement, setRouteAnnouncement] = useState("");

  const routeMeta = resolveRouteMetadata(pathname);
  const isExamFocusMode = examFocusModeOverride ?? routeMeta.examFocusMode ?? false;
  const isLoginRoute = pathname === "/";

  const focusPrimaryContent = () => {
    const mainEl = mainRef.current;
    if (!mainEl) {
      return;
    }
    const heading = mainEl.querySelector<HTMLElement>("h1");
    if (heading) {
      if (!heading.hasAttribute("tabindex")) {
        heading.setAttribute("tabindex", "-1");
      }
      heading.focus();
      return;
    }
    if (!mainEl.hasAttribute("tabindex")) {
      mainEl.setAttribute("tabindex", "-1");
    }
    mainEl.focus();
  };

  useEffect(() => {
    document.title = routeMeta.title;

    if (isFirstRenderRef.current) {
      isFirstRenderRef.current = false;
      return;
    }

    setRouteAnnouncement(`Navigated to ${routeMeta.announcement}`);
    focusPrimaryContent();
  }, [routeMeta.title, routeMeta.announcement]);

  const handleSkipToMain = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    focusPrimaryContent();
  };

  return (
    <div className="flex min-h-dvh flex-col bg-background text-foreground">
      <a
        href="#main-content"
        onClick={handleSkipToMain}
        className="skip-link visually-hidden"
      >
        Skip to main content
      </a>

      <AppHeader
        examFocusMode={isExamFocusMode}
        examTitle={examTitle}
        examHeaderSlot={examHeaderSlot}
      />

      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {routeAnnouncement}
      </div>

      <main
        id="main-content"
        ref={mainRef}
        className={cn(
          "mx-auto w-full flex-1 px-4 outline-none sm:px-6",
          isExamFocusMode
            ? "max-w-4xl py-5 sm:py-6"
            : isLoginRoute
              ? "max-w-none p-0"
              : "max-w-7xl py-6 sm:py-10 lg:py-12",
        )}
      >
        <ErrorBoundary resetKeys={[pathname]}>
          <Outlet />
        </ErrorBoundary>
      </main>

      {!isExamFocusMode && !isLoginRoute ? (
        <footer className="border-t border-border bg-card">
          <div className="mx-auto flex max-w-7xl flex-col gap-2 px-4 py-5 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between sm:px-6">
            <p>Examination Hub — Digital Assessment Platform</p>
            <p>Calm &amp; Focused Online Assessment</p>
          </div>
        </footer>
      ) : null}
    </div>
  );
}
