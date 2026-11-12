import { LogOut, Menu, ShieldCheck } from "lucide-react";
import {
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { NavLink, useLocation } from "react-router-dom";

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
  const menuId = useId();
  const { pathname } = useLocation();
  const headerRef = useRef<HTMLElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const lastCollapsedWidthRef = useRef<number>(0);

  const [isWide, setIsWide] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);
  const [isSigningOut, setIsSigningOut] = useState(false);

  const isAuthenticated = Boolean(auth?.sessionUser && auth?.identity);
  const role = auth?.identity?.role ?? null;
  const authNavKey = isAuthenticated && role ? role : "anon";

  const navItems = useMemo<readonly HeaderNavItem[]>(() => {
    if (!isAuthenticated || !role) {
      return [];
    }
    if (role === "ADMIN") {
      return [
        { to: "/admin", label: "Examinations", end: true },
        { to: "/admin/exams/new", label: "Create Examination", end: false },
      ];
    }
    return [{ to: "/student", label: "Examinations", end: true }];
  }, [isAuthenticated, role]);

  const userLabel =
    auth?.identity?.display_name?.trim() ||
    auth?.identity?.email?.trim() ||
    "Signed in";

  // Sync popover attribute cleanly via setAttribute/removeAttribute (never IDL property)
  useLayoutEffect(() => {
    const menuEl = menuRef.current;
    if (!menuEl || examFocusMode || !isAuthenticated) {
      setIsWide(false);
      setIsMenuOpen(false);
      return;
    }

    if (isWide) {
      menuEl.removeAttribute("popover");
      setIsMenuOpen(false);
    } else {
      menuEl.setAttribute("popover", "auto");
    }
  }, [isWide, examFocusMode, isAuthenticated, authNavKey]);

  // Measure natural inline fit with ResizeObserver without layout thrashing
  useEffect(() => {
    lastCollapsedWidthRef.current = 0;

    if (examFocusMode || !isAuthenticated) {
      return;
    }

    const headerEl = headerRef.current;
    const innerEl = innerRef.current;
    const menuEl = menuRef.current;
    if (!headerEl || !innerEl || !menuEl) {
      return;
    }

    let rafId = 0;

    const measureLayout = (forceMeasure: boolean) => {
      const currentWidth = headerEl.clientWidth;
      if (!forceMeasure && !headerEl.classList.contains("is-wide")) {
        if (currentWidth <= lastCollapsedWidthRef.current) {
          return;
        }
      }

      const wasOpen =
        menuEl.matches(":popover-open") || menuEl.classList.contains(":popover-open");
      if (wasOpen && typeof menuEl.hidePopover === "function") {
        menuEl.hidePopover();
      }

      headerEl.classList.add("is-measuring", "is-wide");
      menuEl.removeAttribute("popover");

      const fitsInline = innerEl.scrollWidth <= innerEl.clientWidth + 1;

      if (fitsInline) {
        setIsWide(true);
      } else {
        lastCollapsedWidthRef.current = currentWidth;
        headerEl.classList.remove("is-wide");
        menuEl.setAttribute("popover", "auto");
        setIsWide(false);
        if (wasOpen && typeof menuEl.showPopover === "function") {
          menuEl.showPopover();
        }
      }

      window.cancelAnimationFrame(rafId);
      rafId = window.requestAnimationFrame(() => {
        headerEl.classList.remove("is-measuring");
      });
    };

    measureLayout(true);

    const observer = new ResizeObserver(() => {
      measureLayout(false);
    });
    observer.observe(headerEl);
    observer.observe(menuEl);

    return () => {
      window.cancelAnimationFrame(rafId);
      observer.disconnect();
    };
  }, [examFocusMode, isAuthenticated, authNavKey]);

  // Track native popover toggle events to synchronize aria-expanded
  useEffect(() => {
    const menuEl = menuRef.current;
    if (!menuEl || examFocusMode || !isAuthenticated) {
      return;
    }

    const handleToggle = (event: Event) => {
      const toggleEvent = event as Event & { newState?: string };
      setIsMenuOpen(toggleEvent.newState === "open");
    };

    menuEl.addEventListener("toggle", handleToggle);
    return () => {
      menuEl.removeEventListener("toggle", handleToggle);
    };
  }, [examFocusMode, isAuthenticated, authNavKey]);

  // Close mobile popover cleanly after route selection
  useEffect(() => {
    const menuEl = menuRef.current;
    if (!menuEl || isWide || examFocusMode || !isAuthenticated) {
      return;
    }
    if (
      (menuEl.matches(":popover-open") || menuEl.classList.contains(":popover-open")) &&
      typeof menuEl.hidePopover === "function"
    ) {
      menuEl.hidePopover();
    }
  }, [pathname, isWide, examFocusMode, isAuthenticated, authNavKey]);

  const handleSignOut = async () => {
    if (!auth || isSigningOut) {
      return;
    }
    const menuEl = menuRef.current;
    if (
      menuEl &&
      (menuEl.matches(":popover-open") || menuEl.classList.contains(":popover-open")) &&
      typeof menuEl.hidePopover === "function"
    ) {
      menuEl.hidePopover();
    }
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
        <div className="mx-auto flex min-h-16 max-w-4xl flex-wrap items-center justify-between gap-3 px-4 py-2 sm:px-6">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
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
    <header
      ref={headerRef}
      className={cn(
        "site-header sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-xs",
        isAuthenticated && isWide && "is-wide",
      )}
    >
      <div
        ref={innerRef}
        className="header-inner mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-3 px-4 sm:gap-4 sm:px-6"
      >
        <div className="flex min-w-0 items-center gap-3">
          <NavLink
            to="/"
            className="inline-flex min-h-11 items-center gap-2.5 rounded-md px-1.5 text-base font-semibold tracking-tight text-foreground no-underline hover:text-primary"
          >
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <span>Examination Hub</span>
          </NavLink>
        </div>

        {isAuthenticated ? (
          <nav className="site-nav flex items-center" aria-label="Primary">
            <button
              type="button"
              className="menu-button inline-flex min-h-[44px] min-w-[44px] cursor-pointer items-center gap-2 rounded-md border border-input bg-card px-3.5 text-sm font-medium text-foreground hover:bg-muted"
              aria-controls={menuId}
              aria-expanded={isMenuOpen}
              popoverTarget={menuId}
              popoverTargetAction="toggle"
            >
              <Menu className="size-4" aria-hidden="true" />
              <span>Menu</span>
            </button>

            <ul ref={menuRef} id={menuId} className="site-menu list-none">
              {navItems.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={item.end}
                    className="nav-item-link flex min-h-[44px] items-center rounded-md border border-transparent px-3.5 py-2.5 text-sm font-medium text-foreground no-underline transition-colors hover:bg-muted"
                  >
                    {item.label}
                  </NavLink>
                </li>
              ))}

              <li className="border-t border-border px-3.5 py-2 text-xs text-muted-foreground [.site-header.is-wide_&]:ml-2 [.site-header.is-wide_&]:border-t-0 [.site-header.is-wide_&]:border-l [.site-header.is-wide_&]:py-1 [.site-header.is-wide_&]:pl-3.5">
                <span
                  className="block max-w-48 truncate font-medium text-foreground"
                  title={userLabel}
                >
                  {userLabel}
                </span>
              </li>

              <li>
                <button
                  type="button"
                  disabled={isSigningOut}
                  onClick={() => void handleSignOut()}
                  className="inline-flex min-h-[44px] w-full cursor-pointer items-center gap-2 rounded-md border border-input bg-card px-3.5 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60 [.site-header.is-wide_&]:w-auto"
                >
                  <LogOut className="size-4" aria-hidden="true" />
                  <span>{isSigningOut ? "Signing out..." : "Sign out"}</span>
                </button>
              </li>
            </ul>
          </nav>
        ) : null}
      </div>
    </header>
  );
}
