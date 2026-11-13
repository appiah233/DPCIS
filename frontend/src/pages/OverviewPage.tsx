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
  "One question at a time",
  "Your answers save as you work",
  "Results after your sitting ends",
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
            A secure and focused place to take your examinations and view your results.
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
    <div className="auth-stage grid min-h-[calc(100dvh-4rem)] w-full bg-card lg:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
      <section className="auth-story relative isolate flex min-h-[380px] flex-col justify-end overflow-hidden px-6 py-7 text-white sm:px-10 sm:py-10 lg:min-h-[calc(100dvh-4rem)] lg:px-14 lg:py-12">
        <img
          src="/images/student-study-hero.png"
          alt="University students studying together in a library"
          className="auth-story-image absolute inset-0 h-full w-full object-cover"
        />

        <div className="auth-reveal auth-reveal-late relative z-10 max-w-2xl space-y-4 lg:space-y-6">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/30 bg-black/20 px-3 py-1.5 text-xs font-medium text-white backdrop-blur-sm"><span className="size-1.5 rounded-full bg-rose-200" />A space to do your best</span>
          <h1 tabIndex={-1} className="max-w-[13ch] text-4xl leading-[1.04] font-semibold tracking-[-0.045em] outline-none sm:text-5xl lg:text-[clamp(3.25rem,4.5vw,5.5rem)]">
            Own the moment. Show what you know<span className="text-rose-200">.</span>
          </h1>
          <p className="max-w-lg text-sm leading-7 text-white/90 sm:text-base">
            Focus on each question. We&apos;ll keep your progress safe while you work.
          </p>
          {isConfigured ? (
            <ul aria-label="Examination experience highlights" className="hidden gap-x-6 gap-y-2 text-sm text-white/90 sm:grid sm:grid-cols-2">
              {REASSURANCE_ITEMS.map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-rose-200" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </section>

      <section aria-label="Account access" className="auth-form-column flex min-w-0 flex-col justify-center gap-6 px-5 py-8 sm:px-10 sm:py-12 lg:px-[clamp(2rem,5vw,5rem)]">
        {healthState.kind === "unreachable" ? (
          <Alert variant="warning" role="status">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 space-y-1">
                <AlertTitle>We&apos;re having trouble connecting to Examination Hub.</AlertTitle>
                <AlertDescription>Please check your connection and try again.</AlertDescription>
              </div>
              <Button type="button" variant="outline" className="min-h-[44px] shrink-0" onClick={() => void refreshHealth()}>Try Again</Button>
            </div>
          </Alert>
        ) : null}
        <AuthBoundary onAuthSuccess={refreshAuth} />
        <p className="text-center text-xs text-muted-foreground">Your session and examination progress are protected.</p>
      </section>
    </div>
  );
}
