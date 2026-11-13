import { ArrowRight, BookOpenCheck, Clock3, History, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  EmptyStatePanel,
  ErrorStatePanel,
  LoadingStatePanel,
} from "@/components/ui/state-panel";
import { useOptionalAuth } from "@/features/auth/useAuth";
import { StudentExamCard } from "@/features/student/StudentExamCard";
import { StudentHistorySection } from "@/features/student/StudentHistorySection";
import { formatStudentErrorMessage } from "@/features/student/formatters";
import {
  listAvailableExams,
  listStudentAttempts,
} from "@/features/student/studentApi";
import type {
  ExamStudentOut,
  StudentAttemptSummary,
} from "@/types/studentExam";

interface DashboardState {
  status: "loading" | "ready" | "error";
  exams: ExamStudentOut[];
  attempts: StudentAttemptSummary[];
  errorMessage: string | null;
}

export function StudentDashboardPage() {
  const auth = useOptionalAuth();
  const [state, setState] = useState<DashboardState>({
    status: "loading",
    exams: [],
    attempts: [],
    errorMessage: null,
  });
  const [reloadNonce, setReloadNonce] = useState(0);

  const handleRefresh = useCallback(() => {
    setReloadNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setState((prev) => ({
      ...prev,
      status: "loading",
      errorMessage: null,
    }));

    Promise.all([
      listAvailableExams({ signal: controller.signal }),
      listStudentAttempts({ signal: controller.signal }),
    ])
      .then(([exams, attempts]) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          status: "ready",
          exams,
          attempts,
          errorMessage: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState((prev) => ({
          ...prev,
          status: "error",
          errorMessage: formatStudentErrorMessage(
            error,
            "Unable to load your examinations right now.",
          ),
        }));
      });

    return () => {
      controller.abort();
    };
  }, [reloadNonce]);

  const activeExamWithAttempt = state.exams.find((exam) => Boolean(exam.active_attempt_id));
  const activeAttemptRow = state.attempts.find(
    (attempt) => attempt.status === "IN_PROGRESS",
  );
  const resumeAttemptId =
    activeExamWithAttempt?.active_attempt_id ?? activeAttemptRow?.attempt_id ?? null;
  const resumeExamTitle =
    activeExamWithAttempt?.title ?? activeAttemptRow?.exam_title ?? "Examination in progress";

  const studentLabel =
    auth?.identity?.display_name ??
    auth?.identity?.email ??
    auth?.sessionUser?.name ??
    auth?.sessionUser?.email ??
    null;
  const availableCount = state.exams.filter((exam) => exam.can_start).length;
  const finishedCount = state.attempts.filter((attempt) => attempt.status !== "IN_PROGRESS").length;
  const nextExam = state.exams.find((exam) => exam.can_start);

  return (
    <div className="space-y-9 pb-8 sm:space-y-11">
      <section className="portal-hero portal-hero-student portal-reveal grid gap-8 px-6 py-8 sm:px-10 sm:py-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(270px,0.7fr)] lg:gap-12 lg:px-12 lg:py-12">
        <div className="min-w-0 space-y-6">
          <p className="portal-eyebrow">Your student workspace</p>
          <div className="space-y-4">
            <h1 tabIndex={-1} className="max-w-2xl text-4xl font-bold leading-[1.08] tracking-[-0.045em] outline-none sm:text-5xl lg:text-6xl">
              A clear path to your next achievement.
            </h1>
            <p className="max-w-xl text-base leading-relaxed text-slate-200 sm:text-lg">
              {studentLabel ? `Welcome back, ${studentLabel}. ` : "Welcome back. "}
              Find your examinations, pick up a sitting, and review your completed work in one place.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button type="button" variant="outline" onClick={handleRefresh} disabled={state.status === "loading"} className="border-white/35 bg-white/10 text-white hover:bg-white/20 hover:text-white">
              <RefreshCw className={state.status === "loading" ? "size-4 animate-spin motion-reduce:animate-none" : "size-4"} aria-hidden="true" />
              <span>Refresh workspace</span>
            </Button>
          </div>
        </div>
        <div className="flex min-w-0 flex-col justify-between rounded-2xl border border-white/20 bg-white/10 p-6 backdrop-blur-sm sm:p-7">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-white/15 text-white">
            {resumeAttemptId ? <Clock3 className="size-6" aria-hidden="true" /> : <BookOpenCheck className="size-6" aria-hidden="true" />}
          </div>
          <div className="mt-8 space-y-3">
            <p className="portal-eyebrow">{state.status === "loading" ? "Getting ready" : resumeAttemptId ? "Continue your sitting" : "Your next step"}</p>
            <h2 className="break-words text-2xl font-semibold leading-tight tracking-tight sm:text-3xl">
              {state.status === "loading" ? "Loading your workspace" : state.status === "error" ? "Workspace unavailable" : resumeAttemptId ? resumeExamTitle : nextExam?.title ?? "You're all caught up"}
            </h2>
            <p className="text-sm leading-relaxed text-slate-200">
              {state.status === "loading" ? "Finding your examinations and recent sessions." : state.status === "error" ? "Please try refreshing your workspace." : resumeAttemptId
                ? "Your timer continues while you're away. Return to your examination when you're ready."
                : nextExam
                  ? `${nextExam.question_count} questions · ${nextExam.duration_minutes} minutes. Review the instructions before you begin.`
                  : "New examinations will appear here when your administrator publishes them."}
            </p>
          </div>
          {state.status === "ready" && resumeAttemptId ? (
            <Button asChild className="mt-6 w-full justify-between bg-white text-slate-900 hover:bg-slate-100">
              <Link to={`/student/attempts/${encodeURIComponent(resumeAttemptId)}`}>Resume examination <ArrowRight className="size-4" aria-hidden="true" /></Link>
            </Button>
          ) : state.status === "ready" && nextExam ? (
            <Button asChild className="mt-6 w-full justify-between bg-white text-slate-900 hover:bg-slate-100">
              <Link to={`/student/exams/${encodeURIComponent(nextExam.id)}`}>View examination <ArrowRight className="size-4" aria-hidden="true" /></Link>
            </Button>
          ) : null}
        </div>
      </section>

      {state.status === "loading" ? <LoadingStatePanel label="Loading available examinations and history..." cards={3} /> : null}
      {state.status === "error" ? (
        <ErrorStatePanel title="Could not load your examinations" message={state.errorMessage ?? "We could not load your examinations right now. Please try again."} onRetry={handleRefresh} />
      ) : null}

      {state.status === "ready" ? (
        <>
          <dl className="grid gap-3 sm:grid-cols-3 sm:gap-4">
            {([
              { label: "Ready to start", value: availableCount, icon: BookOpenCheck, note: "Published examinations" },
              { label: "Past sessions", value: finishedCount, icon: History, note: "Submitted sittings" },
              { label: "In progress", value: resumeAttemptId ? 1 : 0, icon: Clock3, note: "Active sitting" },
            ] as const).map((item) => (
              <div key={item.label} className="portal-stat flex items-center justify-between gap-4 px-5 py-5 sm:px-6 sm:py-6">
                <div>
                  <dt className="text-sm font-medium text-muted-foreground">{item.label}</dt>
                  <dd className="mt-1 text-3xl font-bold tabular-nums tracking-tight text-foreground">{item.value}</dd>
                  <p className="mt-1 text-xs text-muted-foreground">{item.note}</p>
                </div>
                <span className="flex size-11 shrink-0 items-center justify-center rounded-2xl bg-red-50 text-primary"><item.icon className="size-5" aria-hidden="true" /></span>
              </div>
            ))}
          </dl>

          <section aria-labelledby="published-exams-heading" className="space-y-5">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div>
                <p className="mb-1 text-xs font-bold uppercase tracking-[0.16em] text-primary">Your opportunities</p>
                <h2 id="published-exams-heading" className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Available examinations</h2>
              </div>
              <span className="rounded-full border border-border bg-white px-3 py-1 text-sm font-medium text-muted-foreground">{state.exams.length} listed</span>
            </div>
            {state.exams.length === 0 ? (
              <EmptyStatePanel icon={<BookOpenCheck className="size-5" aria-hidden="true" />} title="No available examinations right now" description="When an examination is available for you, it will appear here." />
            ) : (
              <div className="card-grid">
                {state.exams.map((exam) => <StudentExamCard key={exam.id} exam={exam} />)}
              </div>
            )}
          </section>

          <section aria-labelledby="attempt-history-heading" className="space-y-5">
            <div>
              <p className="mb-1 text-xs font-bold uppercase tracking-[0.16em] text-primary">Your record</p>
              <h2 id="attempt-history-heading" className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">Examination history</h2>
            </div>
            <div className="portal-panel overflow-hidden"><StudentHistorySection attempts={state.attempts} /></div>
          </section>
        </>
      ) : null}
    </div>
  );
}
