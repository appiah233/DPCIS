import { Menu, ShieldCheck } from "lucide-react";
import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { to: "/", label: "Overview", end: true },
  { to: "/student", label: "Student", end: false },
  { to: "/admin", label: "Admin", end: false },
] as const;

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
  const menuId = useId();
  const { pathname } = useLocation();
  const headerRef = useRef<HTMLElement>(null);
  const innerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLUListElement>(null);
  const lastCollapsedWidthRef = useRef<number>(0);

  const [isWide, setIsWide] = useState(false);
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  // Sync popover attribute cleanly via setAttribute/removeAttribute (never IDL property)
  useLayoutEffect(() => {
    const menuEl = menuRef.current;
    if (!menuEl || examFocusMode) {
      return;
    }

    if (isWide) {
      menuEl.removeAttribute("popover");
      setIsMenuOpen(false);
    } else {
      menuEl.setAttribute("popover", "auto");
    }
  }, [isWide, examFocusMode]);

  // Measure natural inline fit with ResizeObserver without layout thrashing
  useEffect(() => {
    if (examFocusMode) {
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
  }, [examFocusMode]);

  // Track native popover toggle events to synchronize aria-expanded
  useEffect(() => {
    const menuEl = menuRef.current;
    if (!menuEl || examFocusMode) {
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
  }, [examFocusMode]);

  // Close mobile popover cleanly after route selection
  useEffect(() => {
    const menuEl = menuRef.current;
    if (!menuEl || isWide || examFocusMode) {
      return;
    }
    if (
      (menuEl.matches(":popover-open") || menuEl.classList.contains(":popover-open")) &&
      typeof menuEl.hidePopover === "function"
    ) {
      menuEl.hidePopover();
    }
  }, [pathname, isWide, examFocusMode]);

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
        isWide && "is-wide",
      )}
    >
      <div
        ref={innerRef}
        className="header-inner mx-auto flex min-h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6"
      >
        <div className="flex items-center gap-3">
          <NavLink
            to="/"
            className="inline-flex min-h-11 items-center gap-2.5 rounded-md px-1.5 text-base font-semibold tracking-tight text-foreground no-underline hover:text-primary"
          >
            <span className="inline-flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <span>Examination Hub</span>
          </NavLink>
          <Badge variant="accent" className="hidden sm:inline-flex">
            Assessment Portal
          </Badge>
        </div>

        <nav className="site-nav flex items-center" aria-label="Primary">
          <button
            type="button"
            className="menu-button inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-md border border-input bg-card px-3.5 text-sm font-medium text-foreground hover:bg-muted"
            aria-controls={menuId}
            aria-expanded={isMenuOpen}
            {...({
              popovertarget: menuId,
              popovertargetaction: "toggle",
            } as Record<string, string>)}
          >
            <Menu className="size-4" aria-hidden="true" />
            <span>Menu</span>
          </button>

          <ul ref={menuRef} id={menuId} className="site-menu list-none">
            {NAV_ITEMS.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.end}
                  className="nav-item-link flex min-h-11 items-center rounded-md border border-transparent px-3.5 py-2.5 text-sm font-medium text-foreground no-underline transition-colors hover:bg-muted"
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </header>
  );
}
