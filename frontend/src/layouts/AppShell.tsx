import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from "react";
import { Outlet, useLocation } from "react-router-dom";

import { ErrorBoundary } from "@/components/ErrorBoundary";
import { useOptionalAuth } from "@/features/auth/useAuth";
import { AdminLayout } from "@/layouts/AdminLayout";
import { FocusLayout } from "@/layouts/FocusLayout";
import { PublicLayout } from "@/layouts/PublicLayout";
import { StudentLayout } from "@/layouts/StudentLayout";
import { resolveRouteMetadata } from "@/layouts/routeMetadata";

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
  const auth = useOptionalAuth();
  const mainRef = useRef<HTMLElement>(null);
  const isFirstRenderRef = useRef(true);
  const [routeAnnouncement, setRouteAnnouncement] = useState("");

  const routeMeta = resolveRouteMetadata(pathname);
  const isExamFocusMode = examFocusModeOverride ?? routeMeta.examFocusMode ?? false;

  const isAuthenticated = Boolean(auth?.sessionUser && auth?.identity);
  const role = auth?.identity?.role ?? null;

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

  const content = (
    <ErrorBoundary resetKeys={[pathname]}>
      <Outlet />
    </ErrorBoundary>
  );

  const renderShell = () => {
    if (isExamFocusMode) {
      return (
        <FocusLayout
          mainRef={mainRef}
          examTitle={examTitle}
          examHeaderSlot={examHeaderSlot}
        >
          {content}
        </FocusLayout>
      );
    }

    if (pathname.startsWith("/admin")) {
      return <AdminLayout mainRef={mainRef}>{content}</AdminLayout>;
    }

    if (pathname.startsWith("/student")) {
      return <StudentLayout mainRef={mainRef}>{content}</StudentLayout>;
    }

    if (pathname !== "/" && isAuthenticated && role === "ADMIN") {
      return <AdminLayout mainRef={mainRef}>{content}</AdminLayout>;
    }

    if (pathname !== "/" && isAuthenticated && role === "STUDENT") {
      return <StudentLayout mainRef={mainRef}>{content}</StudentLayout>;
    }

    return <PublicLayout mainRef={mainRef}>{content}</PublicLayout>;
  };

  return (
    <>
      <a
        href="#main-content"
        onClick={handleSkipToMain}
        className="skip-link visually-hidden"
      >
        Skip to main content
      </a>

      <div className="visually-hidden" aria-live="polite" aria-atomic="true">
        {routeAnnouncement}
      </div>

      {renderShell()}
    </>
  );
}
