import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Info,
  Lock,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ErrorStatePanel,
  LoadingStatePanel,
} from "@/components/ui/state-panel";
import {
  formatDecimalValue,
  formatDurationMinutes,
  formatStudentErrorMessage,
} from "@/features/student/formatters";
import {
  getStudentExamDetail,
  startOrResumeAttempt,
} from "@/features/student/studentApi";
import type { ExamStudentOut } from "@/types/studentExam";

interface InstructionsState {
  status: "loading" | "ready" | "error";
  exam: ExamStudentOut | null;
  errorMessage: string | null;
}

export function StudentExamInstructionsPage() {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();

  const [state, setState] = useState<InstructionsState>({
    status: "loading",
    exam: null,
    errorMessage: null,
  });
  const [reloadNonce, setReloadNonce] = useState(0);
  const [isStarting, setIsStarting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const startingLockRef = useRef(false);

  const handleRetry = useCallback(() => {
    setReloadNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!examId) {
      setState({
        status: "error",
        exam: null,
        errorMessage: "No examination identifier was provided.",
      });
      return;
    }

    const controller = new AbortController();
    setState({
      status: "loading",
      exam: null,
      errorMessage: null,
    });
    setStartError(null);

    getStudentExamDetail(examId, { signal: controller.signal })
      .then((exam) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          status: "ready",
          exam,
          errorMessage: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          status: "error",
          exam: null,
          errorMessage: formatStudentErrorMessage(
            error,
            "Unable to load examination instructions.",
          ),
        });
      });

    return () => {
      controller.abort();
    };
  }, [examId, reloadNonce]);

  const handleStartOrResume = async () => {
    if (!state.exam || !state.exam.can_start || startingLockRef.current) {
      return;
    }

    startingLockRef.current = true;
    setIsStarting(true);
    setStartError(null);

    try {
      const started = await startOrResumeAttempt(state.exam.id);
      navigate(`/student/attempts/${encodeURIComponent(started.attempt_id)}`);
    } catch (error) {
      setStartError(
        formatStudentErrorMessage(
          error,
          "Could not start the examination. Please try again.",
        ),
      );
      startingLockRef.current = false;
      setIsStarting(false);
    }
  };

  if (state.status === "loading") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Examination Briefing"
          title="Loading Examination Details"
          description="Loading examination details and instructions..."
          action={
            <Button asChild variant="outline">
              <Link to="/student">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Back to dashboard</span>
              </Link>
            </Button>
          }
        />
        <LoadingStatePanel label="Loading examination instructions..." cards={1} />
      </div>
    );
  }

  if (state.status === "error" || !state.exam) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Examination Briefing"
          title="Examination Unavailable"
          description="We could not retrieve this examination briefing."
          action={
            <Button asChild variant="outline">
              <Link to="/student">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Back to dashboard</span>
              </Link>
            </Button>
          }
        />
        <ErrorStatePanel
          title="Unable to load examination instructions"
          message={state.errorMessage ?? "This examination may no longer be published."}
          onRetry={handleRetry}
          action={
            <Button asChild variant="outline">
              <Link to="/student">Return to dashboard</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const exam = state.exam;
  const hasActiveAttempt = Boolean(exam.active_attempt_id);
  const attemptsRemaining = Math.max(0, exam.max_attempts - exam.attempts_used);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow="Examination Briefing"
        title={exam.title}
        description={
          exam.description ??
          "Review the duration, pass mark, and instructions before starting your timed sitting."
        }
        action={
          <Button asChild variant="outline">
            <Link to="/student">
              <ArrowLeft className="size-4" aria-hidden="true" />
              <span>Back to dashboard</span>
            </Link>
          </Button>
        }
      />

      {startError ? (
        <ErrorStatePanel
          title="Could not start examination"
          message={startError}
          onRetry={() => void handleStartOrResume()}
        />
      ) : null}

      <Card>
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle as="h2">Examination Summary</CardTitle>
            {hasActiveAttempt ? (
              <Badge variant="accent">
                <Clock className="size-3.5" aria-hidden="true" />
                <span>In progress</span>
              </Badge>
            ) : !exam.can_start ? (
              <Badge variant="secondary">
                <Lock className="size-3.5" aria-hidden="true" />
                <span>Maximum attempts reached</span>
              </Badge>
            ) : null}
          </div>
          <CardDescription>
            Your time limit and saved answers are tracked automatically throughout your sitting.
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          <dl className="grid grid-cols-1 gap-3 rounded-lg border border-border bg-muted/40 p-4 sm:grid-cols-2">
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">Duration</dt>
              <dd className="mt-0.5 text-base font-semibold tabular-nums text-foreground">
                {formatDurationMinutes(exam.duration_minutes)}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">Questions</dt>
              <dd className="mt-0.5 text-base font-semibold tabular-nums text-foreground">
                {exam.question_count} multiple-choice{" "}
                {exam.question_count === 1 ? "question" : "questions"}
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">Pass mark</dt>
              <dd className="mt-0.5 text-base font-semibold tabular-nums text-foreground">
                {formatDecimalValue(exam.pass_mark)}%
              </dd>
            </div>
            <div className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">Attempts</dt>
              <dd className="mt-0.5 text-base font-semibold tabular-nums text-foreground">
                {exam.attempts_used} used of {exam.max_attempts} ({attemptsRemaining}{" "}
                remaining)
              </dd>
            </div>
          </dl>

          <section aria-labelledby="instructions-content-heading" className="space-y-2">
            <h3
              id="instructions-content-heading"
              className="text-base font-semibold text-foreground"
            >
              Instructions
            </h3>
            {exam.instructions ? (
              <p className="whitespace-pre-line text-sm leading-relaxed text-foreground sm:text-base">
                {exam.instructions}
              </p>
            ) : (
              <p className="text-sm leading-relaxed text-muted-foreground sm:text-base">
                Select one option for each question. You can move freely between questions and
                review all responses before submitting.
              </p>
            )}
          </section>

          <Alert variant="default">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
              <div className="space-y-1">
                <AlertTitle>Timed session &amp; automatic save</AlertTitle>
                <AlertDescription>
                  <ul className="mt-1 list-disc space-y-1 pl-4">
                    <li>
                      Your answers are saved automatically as soon as you select an option.
                    </li>
                    <li>
                      Refreshing or reopening the browser restores your saved answers, while your
                      exam timer continues uninterrupted.
                    </li>
                    <li>
                      When time reaches zero, your recorded answers are locked and submitted
                      automatically.
                    </li>
                  </ul>
                </AlertDescription>
              </div>
            </div>
          </Alert>

          {!exam.show_result ? (
            <Alert variant="default">
              <div className="flex items-start gap-3">
                <Info className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div>
                  <AlertTitle>Score disclosure policy</AlertTitle>
                  <AlertDescription>
                    After you submit, you will receive confirmation that your examination was
                    recorded. Detailed scores are not shown for this examination.
                  </AlertDescription>
                </div>
              </div>
            </Alert>
          ) : null}
        </CardContent>

        <CardFooter className="justify-between">
          {isStarting ? (
            <Button type="button" variant="outline" disabled>
              Cancel
            </Button>
          ) : (
            <Button asChild variant="outline">
              <Link to="/student">Cancel</Link>
            </Button>
          )}

          <Button
            type="button"
            variant="default"
            size="lg"
            disabled={isStarting || !exam.can_start}
            onClick={() => void handleStartOrResume()}
          >
            <span>
              {isStarting
                ? hasActiveAttempt
                  ? "Resuming..."
                  : "Starting..."
                : hasActiveAttempt
                  ? "Resume Examination"
                  : "Start Examination"}
            </span>
            <ArrowRight className="size-4" aria-hidden="true" />
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
