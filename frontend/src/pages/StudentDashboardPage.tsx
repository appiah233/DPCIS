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
    <div className="space-y-6 pb-8">
      <div className="student-page-heading">
        <div><small>Student workspace</small><h1 tabIndex={-1}>Welcome back{studentLabel ? ", " + studentLabel.split(" ")[0] : ""}</h1><p>Start an examination, resume a sitting or review your results.</p></div>
        <Button type="button" variant="outline" onClick={handleRefresh} disabled={state.status === "loading"}><RefreshCw className="size-4" aria-hidden="true" />Refresh</Button>
      </div>
      <section className="student-spotlight">
        <div className="min-w-0 space-y-6">
          <span className="student-spotlight-label"><BookOpenCheck className="size-4" aria-hidden="true" />{resumeAttemptId ? "Sitting in progress" : nextExam ? "Ready when you are" : "Nothing due"}</span>
          <h2>{state.status === "loading" ? "Loading your workspace" : resumeAttemptId ? resumeExamTitle : nextExam?.title ?? "You’re all caught up"}</h2>
          <p>{resumeAttemptId ? "Your timer continues while you’re away. Return to your examination when you’re ready." : nextExam ? "Review the instructions before starting your next examination." : "New examinations appear here as soon as your administrator publishes them."}</p>
        </div>
        <div className="student-spotlight-score">
          <small>{resumeAttemptId ? "Current sitting" : nextExam ? "Next examination" : "Latest result"}</small>
          <strong>{resumeAttemptId ? "In progress" : nextExam ? `${nextExam.question_count} questions` : state.attempts.find((attempt) => attempt.result_visible)?.percentage != null ? `${state.attempts.find((attempt) => attempt.result_visible)?.percentage}%` : "—"}</strong>
          {state.status === "ready" && resumeAttemptId ? (
            <Button asChild className="mt-4 bg-white text-[#a3123f] hover:bg-[#fdf0f4]">
              <Link to={`/student/attempts/${encodeURIComponent(resumeAttemptId)}`}>Resume examination <ArrowRight className="size-4" aria-hidden="true" /></Link>
            </Button>
          ) : state.status === "ready" && nextExam ? (
            <Button asChild className="mt-4 bg-white text-[#a3123f] hover:bg-[#fdf0f4]">
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
          <div className="student-kpis">
            {([
              { label: "Ready to start", value: availableCount, icon: BookOpenCheck, note: "Published examinations" },
              { label: "Past sessions", value: finishedCount, icon: History, note: "Submitted sittings" },
              { label: "In progress", value: resumeAttemptId ? 1 : 0, icon: Clock3, note: "Active sitting" },
            ] as const).map((item) => (
              <div key={item.label} className="student-card student-kpi">
                <span className="student-kpi-icon"><item.icon className="size-5" aria-hidden="true" /></span><div>
                  <small>{item.label}</small>
                  <strong>{item.value}</strong>
                  <em>{item.note}</em>
                </div>
              </div>
            ))}
          </div>

          <div className="student-dashboard-grid"><section aria-labelledby="published-exams-heading">
            <div className="student-section-title">
              <div>
                <h2 id="published-exams-heading">Available examinations</h2>
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

          <section aria-labelledby="attempt-history-heading">
            <div>
              <div className="student-section-title"><h2 id="attempt-history-heading">Examination history</h2></div>
            </div>
            <div className="student-card overflow-hidden"><StudentHistorySection attempts={state.attempts} /></div>
          </section></div>
        </>
      ) : null}
    </div>
  );
}
