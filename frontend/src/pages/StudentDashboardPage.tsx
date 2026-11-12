import { ArrowRight, BookOpenCheck, Clock, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  EmptyStatePanel,
  ErrorStatePanel,
  LoadingStatePanel,
} from "@/components/ui/state-panel";
import { useOptionalAuth } from "@/features/auth/useAuth";
import { StudentExamCard } from "@/features/student/StudentExamCard";
import { StudentHistorySection } from "@/features/student/StudentHistorySection";
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
          errorMessage:
            error instanceof Error
              ? error.message
              : "Unable to load your examinations right now.",
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

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow={studentLabel ? `Student Workspace · ${studentLabel}` : "Student Workspace"}
        title="Available Examinations"
        description="Start a published examination, resume an unfinished sitting, or review your submitted results."
        action={
          <Button
            type="button"
            variant="outline"
            onClick={handleRefresh}
            disabled={state.status === "loading"}
          >
            <RefreshCw
              className={
                state.status === "loading"
                  ? "size-4 animate-spin motion-reduce:animate-none"
                  : "size-4"
              }
              aria-hidden="true"
            />
            <span>Refresh</span>
          </Button>
        }
      />

      {state.status === "loading" ? (
        <LoadingStatePanel label="Loading available examinations and history..." cards={3} />
      ) : null}

      {state.status === "error" ? (
        <ErrorStatePanel
          title="Could not load student workspace"
          message={state.errorMessage ?? "An unexpected error occurred while contacting the server."}
          onRetry={handleRefresh}
        />
      ) : null}

      {state.status === "ready" ? (
        <>
          {resumeAttemptId ? (
            <Alert variant="warning" role="status">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <Clock className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
                  <div className="min-w-0 space-y-1">
                    <AlertTitle>Examination sitting in progress</AlertTitle>
                    <AlertDescription>
                      You have an active sitting for{" "}
                      <span className="font-semibold">{resumeExamTitle}</span>. Your server timer
                      continues running until submitted or expired.
                    </AlertDescription>
                  </div>
                </div>

                <Button asChild variant="default" className="shrink-0">
                  <Link to={`/student/attempts/${encodeURIComponent(resumeAttemptId)}`}>
                    <span>Resume Examination</span>
                    <ArrowRight className="size-4" aria-hidden="true" />
                  </Link>
                </Button>
              </div>
            </Alert>
          ) : null}

          <section aria-labelledby="published-exams-heading" className="space-y-4">
            <h2
              id="published-exams-heading"
              className="text-lg font-semibold tracking-tight text-foreground sm:text-xl"
            >
              Published Examinations
            </h2>

            {state.exams.length === 0 ? (
              <EmptyStatePanel
                icon={<BookOpenCheck className="size-5" aria-hidden="true" />}
                title="No published examinations right now"
                description="When an instructor publishes an examination for students, it will appear here."
              />
            ) : (
              <div className="card-grid">
                {state.exams.map((exam) => (
                  <StudentExamCard key={exam.id} exam={exam} />
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="attempt-history-heading" className="space-y-4">
            <h2
              id="attempt-history-heading"
              className="text-lg font-semibold tracking-tight text-foreground sm:text-xl"
            >
              Attempt History
            </h2>

            <StudentHistorySection attempts={state.attempts} />
          </section>
        </>
      ) : null}
    </div>
  );
}
