import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { AuthProvider } from "@/features/auth/AuthContext";
import { useAuth, useOptionalAuth } from "@/features/auth/useAuth";
import type { AuthMeResponse } from "@/lib/api";

export type ApplicationRole = AuthMeResponse["role"];

function ProtectedRouteInner({ requiredRole }: { requiredRole: ApplicationRole }) {
  const location = useLocation();
  const {
    isConfigured,
    isLoading,
    sessionUser,
    identity,
    errorMessage,
    refreshAuth,
    signOut,
  } = useAuth();

  if (!isConfigured) {
    return (
      <ErrorStatePanel
        title="Examination Hub is temporarily unavailable"
        message="The authentication service has not been configured for this environment. Please contact the system administrator."
        onRetry={() => void refreshAuth()}
        retryLabel="Try Again"
      />
    );
  }

  if (isLoading) {
    return <LoadingStatePanel label="Checking your session..." cards={1} />;
  }

  if (!sessionUser) {
    return <Navigate to="/" replace state={{ from: location.pathname }} />;
  }

  if (errorMessage || !identity) {
    return (
      <ErrorStatePanel
        title="Unable to open your workspace"
        message={errorMessage ?? "We could not verify your account right now. Please try again."}
        onRetry={() => void refreshAuth()}
        retryLabel="Try Again"
        action={
          <Button
            type="button"
            variant="outline"
            className="min-h-[44px]"
            onClick={() => void signOut()}
          >
            Sign out
          </Button>
        }
      />
    );
  }

  if (identity.role !== requiredRole) {
    const safeHomePath = identity.role === "STUDENT" ? "/student" : "/admin";
    return (
      <ErrorStatePanel
        title="Access denied"
        message="You do not have permission to view this page."
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline" className="min-h-[44px]">
              <Link to={safeHomePath}>Return to My Examinations</Link>
            </Button>
            <Button
              type="button"
              variant="ghost"
              className="min-h-[44px]"
              onClick={() => void signOut()}
            >
              Sign out
            </Button>
          </div>
        }
      />
    );
  }

  return <Outlet />;
}

export function ProtectedRoute({ requiredRole }: { requiredRole: ApplicationRole }) {
  const existingAuth = useOptionalAuth();
  if (existingAuth === null) {
    return (
      <AuthProvider>
        <ProtectedRouteInner requiredRole={requiredRole} />
      </AuthProvider>
    );
  }
  return <ProtectedRouteInner requiredRole={requiredRole} />;
}
