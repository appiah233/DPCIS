import { ArrowUpRight, CheckCircle2, ShieldCheck, Sparkles } from "lucide-react";
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
  "Clear countdown timer during your examination",
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
    <div className="auth-stage grid min-h-[min(760px,calc(100dvh-12rem))] overflow-hidden rounded-[1.75rem] border border-border/70 bg-card shadow-[0_24px_90px_-48px_rgb(24_24_27/0.38)] lg:grid-cols-[minmax(0,1.08fr)_minmax(0,0.92fr)]">
      <section className="auth-story relative isolate flex min-h-[320px] flex-col justify-between overflow-hidden px-6 py-8 text-white sm:px-10 sm:py-10 lg:min-h-[650px] lg:px-12 lg:py-12">
        <div className="auth-story-grid pointer-events-none absolute inset-0" aria-hidden="true" />
        <div className="auth-orbit auth-orbit-one pointer-events-none absolute" aria-hidden="true" />
        <div className="auth-orbit auth-orbit-two pointer-events-none absolute" aria-hidden="true" />
        <div className="auth-orbit-core pointer-events-none absolute" aria-hidden="true"><Sparkles className="size-10" /></div>

        <div className="auth-reveal relative z-10 flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-xl border border-white/25 bg-white/10 shadow-lg shadow-black/10"><ShieldCheck className="size-5" aria-hidden="true" /></span>
          <span className="text-sm font-semibold tracking-[0.16em] uppercase">Examination Hub</span>
        </div>

        <div className="auth-reveal auth-reveal-late relative z-10 max-w-xl space-y-5 lg:space-y-7">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/25 bg-white/10 px-3 py-1.5 text-xs font-medium text-white/90 backdrop-blur-sm"><span className="size-1.5 rounded-full bg-rose-200" />A better way to assess</span>
          <h1 tabIndex={-1} className="max-w-[12ch] text-4xl leading-[1.06] font-semibold tracking-[-0.045em] outline-none sm:text-5xl lg:text-[clamp(3rem,5vw,4.8rem)]">
            Your next chapter starts here<span className="text-rose-200">.</span>
          </h1>
          <p className="max-w-md text-sm leading-7 text-white/80 sm:text-base">
            A clear space to focus, make progress, and finish with confidence.
          </p>
          {isConfigured ? (
            <ul aria-label="Examination experience highlights" className="grid gap-2 text-sm text-white/85 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              {REASSURANCE_ITEMS.map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-rose-200" aria-hidden="true" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="auth-reveal auth-reveal-late relative z-10 hidden items-center gap-2 text-xs font-medium tracking-wide text-white/60 lg:flex">
          MADE FOR FOCUSED LEARNING <ArrowUpRight className="size-4" aria-hidden="true" />
        </div>
      </section>

      <section aria-label="Account access" className="auth-form-column flex min-w-0 flex-col justify-center gap-6 px-5 py-8 sm:px-10 sm:py-12 lg:px-[clamp(2rem,5vw,4.5rem)]">
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
