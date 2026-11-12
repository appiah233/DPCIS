import { CheckCircle2 } from "lucide-react";
import { useEffect } from "react";
import { Navigate } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { AuthBoundary } from "@/features/auth/AuthBoundary";
import { useAuth } from "@/features/auth/useAuth";
import { useHealthCheck } from "@/hooks/useHealthCheck";

const REASSURANCE_ITEMS = [
  "Calm, focused single-question experience",
  "Answers saved automatically as you work",
  "Clear countdown timer throughout your sitting",
  "Results shown when permitted by your administrator",
] as const;

export function OverviewPage() {
  const {
    isConfigured,
    isLoading,
    sessionUser,
    identity,
    errorMessage,
    refreshAuth,
    signOut,
  } = useAuth();
  const { state: healthState, refresh: refreshHealth } = useHealthCheck();

  useEffect(() => {
    if (import.meta.env.DEV && healthState.kind === "unreachable") {
      console.warn(
        "[Examination Hub] Background connectivity check unavailable:",
        healthState.errorMessage,
      );
    }
  }, [healthState]);

  if (isConfigured && isLoading) {
    return (
      <div className="mx-auto max-w-md space-y-6 py-4 sm:py-8">
        <header className="space-y-2 text-center">
          <h1
            tabIndex={-1}
            className="text-2xl font-semibold tracking-tight text-foreground outline-none sm:text-3xl"
          >
            Examination Hub
          </h1>
          <p className="text-sm text-muted-foreground sm:text-base">
            Checking your session...
          </p>
        </header>
        <LoadingStatePanel label="Checking your session..." cards={1} />
      </div>
    );
  }

  if (isConfigured && sessionUser && identity) {
    return <Navigate to={identity.role === "ADMIN" ? "/admin" : "/student"} replace />;
  }

  if (isConfigured && sessionUser && !identity) {
    return (
      <div className="mx-auto max-w-xl space-y-6 py-4 sm:py-8">
        <header className="space-y-2 text-center">
          <h1
            tabIndex={-1}
            className="text-2xl font-semibold tracking-tight text-foreground outline-none sm:text-3xl"
          >
            Examination Hub
          </h1>
          <p className="text-sm text-muted-foreground sm:text-base">
            A focused and secure place to take your examinations.
          </p>
        </header>

        <ErrorStatePanel
          title="We could not open your workspace right now."
          message={errorMessage ?? "Please check your connection and try again."}
          retryLabel="Try Again"
          onRetry={() => void refreshAuth()}
          action={
            <Button type="button" variant="outline" onClick={() => void signOut()}>
              Sign out
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-md space-y-6 py-2 sm:py-6">
      <header className="space-y-2 text-center">
        <h1
          tabIndex={-1}
          className="text-2xl font-semibold tracking-tight text-foreground outline-none sm:text-3xl"
        >
          Examination Hub
        </h1>
        <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
          A focused and secure place to take your examinations.
        </p>
      </header>

      {healthState.kind === "unreachable" ? (
        <Alert variant="warning" role="status">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 space-y-1">
              <AlertTitle>
                We&apos;re having trouble connecting to Examination Hub.
              </AlertTitle>
              <AlertDescription>
                Please check your connection and try again.
              </AlertDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              className="min-h-[44px] shrink-0"
              onClick={() => void refreshHealth()}
            >
              Try Again
            </Button>
          </div>
        </Alert>
      ) : null}

      <AuthBoundary onAuthSuccess={refreshAuth} />

      {isConfigured ? (
        <ul
          aria-label="Examination experience highlights"
          className="grid gap-2.5 px-1 text-sm text-muted-foreground"
        >
          {REASSURANCE_ITEMS.map((item) => (
            <li key={item} className="flex items-start gap-2.5">
              <CheckCircle2
                className="mt-0.5 size-4 shrink-0 text-primary"
                aria-hidden="true"
              />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
