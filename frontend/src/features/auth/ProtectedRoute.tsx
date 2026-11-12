import { Link, Outlet } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { AuthBoundary } from "@/features/auth/AuthBoundary";
import { AuthProvider } from "@/features/auth/AuthContext";
import { useAuth, useOptionalAuth } from "@/features/auth/useAuth";
import type { AuthMeResponse } from "@/lib/api";

export type ApplicationRole = AuthMeResponse["role"];

function ProtectedRouteInner({ requiredRole }: { requiredRole: ApplicationRole }) {
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
      <div className="mx-auto max-w-xl">
        <AuthBoundary />
      </div>
    );
  }

  if (isLoading) {
    return (
      <LoadingStatePanel
        label="Checking authentication session and workspace role..."
        cards={1}
      />
    );
  }

  if (!sessionUser) {
    return (
      <div className="mx-auto max-w-xl">
        <AuthBoundary onAuthSuccess={refreshAuth} />
      </div>
    );
  }

  if (errorMessage || !identity) {
    return (
      <ErrorStatePanel
        title="Unable to verify workspace access"
        message={errorMessage ?? "Unable to load your application identity from the server."}
        onRetry={() => void refreshAuth()}
        action={
          <Button type="button" variant="outline" onClick={() => void signOut()}>
            Sign out
          </Button>
        }
      />
    );
  }

  if (identity.role !== requiredRole) {
    return (
      <ErrorStatePanel
        title="Access restricted"
        message={`This workspace requires the ${requiredRole} role. Your account currently holds the ${identity.role} role.`}
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link to="/">Return to overview</Link>
            </Button>
            <Button type="button" variant="ghost" onClick={() => void signOut()}>
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
