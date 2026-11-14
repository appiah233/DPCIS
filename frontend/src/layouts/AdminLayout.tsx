import { useState, type ReactNode, type RefObject } from "react";
import { NavLink } from "react-router-dom";

import { useOptionalAuth } from "@/features/auth/useAuth";

export interface AdminLayoutProps {
  mainRef: RefObject<HTMLElement | null>;
  children: ReactNode;
}

function getInitials(label: string): string {
  const cleaned = label.trim();
  if (!cleaned) {
    return "AD";
  }
  const parts = cleaned.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return cleaned.slice(0, 2).toUpperCase();
}

export function AdminLayout({ mainRef, children }: AdminLayoutProps) {
  const auth = useOptionalAuth();
  const [isSigningOut, setIsSigningOut] = useState(false);

  const userLabel =
    auth?.identity?.display_name?.trim() ||
    auth?.identity?.email?.trim() ||
    "Dexta Dexta";
  const userInitials = getInitials(userLabel);

  const handleSignOut = async () => {
    if (!auth || isSigningOut) {
      return;
    }
    setIsSigningOut(true);
    try {
      await auth.signOut();
    } finally {
      setIsSigningOut(false);
    }
  };

  return (
    <div className="admin-app">
      <aside className="admin-side" aria-label="Admin console">
        <NavLink to="/admin" className="admin-brand">
          <div className="admin-logo" aria-hidden="true">
            <svg className="admin-icon" viewBox="0 0 24 24">
              <circle cx="12" cy="12" r="9" />
              <circle cx="12" cy="12" r="4" />
            </svg>
          </div>
          <div>
            <b>Examination Hub</b>
            <small>Admin console</small>
          </div>
        </NavLink>

        <div className="admin-nav-h">Management</div>

        <nav className="admin-nav" aria-label="Admin">
          <NavLink
            to="/admin"
            end
            className={({ isActive }) => (isActive ? "on" : undefined)}
          >
            <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="3" y="3" width="7" height="7" rx="1" />
              <rect x="14" y="3" width="7" height="7" rx="1" />
              <rect x="3" y="14" width="7" height="7" rx="1" />
              <rect x="14" y="14" width="7" height="7" rx="1" />
            </svg>
            Overview
          </NavLink>

          <NavLink
            to="/admin/exams"
            className={({ isActive }) => (isActive ? "on" : undefined)}
          >
            <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M2 4h7a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H2zM22 4h-7a3 3 0 0 0-3 3v14a2 2 0 0 1 2-2h8z" />
            </svg>
            Examinations
          </NavLink>

          <NavLink
            to="/admin/results"
            className={({ isActive }) => (isActive ? "on" : undefined)}
          >
            <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
            </svg>
            Results
          </NavLink>
        </nav>

        <div className="admin-user">
          <div className="admin-me">
            <div className="admin-av" aria-hidden="true">
              {userInitials}
            </div>
            <div className="min-w-0">
              <b title={userLabel}>{userLabel}</b>
              <small>Administrator</small>
            </div>
          </div>

          <button
            className="admin-so"
            type="button"
            disabled={isSigningOut}
            onClick={() => void handleSignOut()}
          >
            <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M9 21H5V3h4M16 17l5-5-5-5M21 12H9" />
            </svg>
            {isSigningOut ? "Signing out..." : "Sign out"}
          </button>
        </div>
      </aside>

      <div className="admin-main">
        <main id="main-content" ref={mainRef} className="admin-wrap outline-none">
          {children}
        </main>
        <footer className="admin-footer">Examination Hub, administration</footer>
      </div>
    </div>
  );
}
