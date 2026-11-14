import {
  ArrowLeft,
  Clock,
  Flag,
  Info,
  Lock,
  Save,
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
  const [rulesAcknowledged, setRulesAcknowledged] = useState(false);
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
    <div className="space-y-6">
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

      <div className="student-instructions-grid"><Card>
        <CardHeader className="gap-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle as="h2">Examination rules</CardTitle>
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

        <CardContent className="!p-0">
          <ul className="student-rules">
            <li><span className="student-kpi-icon"><Clock className="size-4" /></span><div><b>The timer can’t be paused</b><span>You have {formatDurationMinutes(exam.duration_minutes)}. When time runs out, your saved answers are submitted automatically.</span></div></li>
            <li><span className="student-kpi-icon"><Save className="size-4" /></span><div><b>Answers save automatically</b><span>A Saved badge confirms each change. Keep this page open and stay online while taking the examination.</span></div></li>
            <li><span className="student-kpi-icon"><Flag className="size-4" /></span><div><b>Move between questions</b><span>Use the question map to return to questions before submitting.</span></div></li>
            <li><span className="student-kpi-icon"><Lock className="size-4" /></span><div><b>Attempts are limited</b><span>You have {attemptsRemaining} {attemptsRemaining === 1 ? "attempt" : "attempts"} remaining.</span></div></li>
            <li><span className="student-kpi-icon"><Info className="size-4" /></span><div><b>Work on your own</b><span>Do not share questions or answers.</span></div></li>
          </ul>
          {exam.instructions ? <section aria-labelledby="instructions-content-heading" className="space-y-2 border-t border-border p-5">
            <h3
              id="instructions-content-heading"
              className="text-base font-semibold text-foreground"
            >
              Instructions
            </h3>
            <p className="whitespace-pre-line text-sm leading-relaxed text-foreground sm:text-base">{exam.instructions}</p>
          </section> : null}

          {!exam.show_result ? (
            <Alert variant="default" className="m-5">
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

        {!hasActiveAttempt ? <label className="student-ack"><input type="checkbox" checked={rulesAcknowledged} onChange={(event) => setRulesAcknowledged(event.target.checked)} />I have read the rules and I’m ready to begin.</label> : null}
      </Card><aside className="student-card student-details"><div className="student-card-heading"><h2>Examination details</h2></div><dl>
        <div className="student-detail-row"><dt>Duration</dt><dd>{formatDurationMinutes(exam.duration_minutes)}</dd></div>
        <div className="student-detail-row"><dt>Questions</dt><dd>{exam.question_count}</dd></div>
        <div className="student-detail-row"><dt>Pass mark</dt><dd>{formatDecimalValue(exam.pass_mark)}%</dd></div>
        <div className="student-detail-row"><dt>Attempts used</dt><dd>{exam.attempts_used} of {exam.max_attempts}</dd></div>
      </dl><div className="p-5"><Button className="w-full" size="lg" disabled={isStarting || !exam.can_start || (!hasActiveAttempt && !rulesAcknowledged)} onClick={() => void handleStartOrResume()}>{isStarting ? "Opening examination…" : hasActiveAttempt ? "Resume examination" : "Start examination"}</Button>{!hasActiveAttempt && !rulesAcknowledged ? <p className="mt-2 text-xs text-muted-foreground">Tick the box to enable Start.</p> : null}</div></aside></div>
    </div>
  );
}
