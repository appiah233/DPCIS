import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  FileCheck2,
  Info,
  Timer,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

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
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { ResultReviewCard } from "@/features/student/ResultReviewCard";
import {
  formatDateTime,
  formatDecimalValue,
  formatPercentage,
  formatStudentErrorMessage,
  formatSubmissionReason,
} from "@/features/student/formatters";
import { getAttemptResult } from "@/features/student/studentApi";
import { ApiClientError } from "@/lib/api";
import type { AttemptResultResponse } from "@/types/studentExam";

interface ResultState {
  status: "loading" | "ready" | "in_progress" | "error";
  result: AttemptResultResponse | null;
  errorMessage: string | null;
}

export function StudentResultPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const location = useLocation();
  const routeNotice =
    location.state &&
    typeof location.state === "object" &&
    "notice" in location.state &&
    typeof (location.state as { notice?: unknown }).notice === "string"
      ? (location.state as { notice: string }).notice
      : null;

  const [state, setState] = useState<ResultState>({
    status: "loading",
    result: null,
    errorMessage: null,
  });
  const [reloadNonce, setReloadNonce] = useState(0);

  const handleRetry = useCallback(() => {
    setReloadNonce((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!attemptId) {
      setState({
        status: "error",
        result: null,
        errorMessage: "No attempt identifier was provided.",
      });
      return;
    }

    const controller = new AbortController();
    setState({
      status: "loading",
      result: null,
      errorMessage: null,
    });

    getAttemptResult(attemptId, { signal: controller.signal })
      .then((result) => {
        if (controller.signal.aborted) {
          return;
        }
        setState({
          status: "ready",
          result,
          errorMessage: null,
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }
        if (error instanceof ApiClientError && error.status === 409) {
          setState({
            status: "in_progress",
            result: null,
            errorMessage: formatStudentErrorMessage(
              error,
              "Submit your active examination before viewing your result.",
            ),
          });
          return;
        }
        setState({
          status: "error",
          result: null,
          errorMessage: formatStudentErrorMessage(
            error,
            "Unable to load examination result.",
          ),
        });
      });

    return () => {
      controller.abort();
    };
  }, [attemptId, reloadNonce]);

  if (state.status === "loading") {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Examination Result"
          title="Loading Attempt Summary"
          description="Loading your examination summary..."
          action={
            <Button asChild variant="outline">
              <Link to="/student">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Back to dashboard</span>
              </Link>
            </Button>
          }
        />
        <LoadingStatePanel label="Loading examination result..." cards={2} />
      </div>
    );
  }

  if (state.status === "in_progress" && attemptId) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Examination Result"
          title="Examination Still In Progress"
          description="This sitting has not been submitted yet."
        />
        <Alert variant="warning" role="status">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-2.5">
              <Clock className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
              <div>
                <AlertTitle>Sitting active</AlertTitle>
                <AlertDescription>
                  {state.errorMessage ??
                    "Submit your active examination before viewing your result."}
                </AlertDescription>
              </div>
            </div>
            <Button asChild variant="default">
              <Link to={`/student/attempts/${encodeURIComponent(attemptId)}`}>
                Resume Examination
              </Link>
            </Button>
          </div>
        </Alert>
      </div>
    );
  }

  if (state.status === "error" || !state.result) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Examination Result"
          title="Result Unavailable"
          description="We could not retrieve this attempt result."
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
          title="Unable to load examination result"
          message={state.errorMessage ?? "The requested result could not be retrieved."}
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

  const result = state.result;
  const isTimerExpired = result.submission_reason === "TIMER_EXPIRED";

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={result.exam_title}
        title="Your result"
        description="Official summary for your completed sitting."
        action={
          <div className="flex gap-2"><Button variant="outline" onClick={() => window.print()}>Print result</Button><Button asChild variant="outline">
            <Link to="/student">
              <ArrowLeft className="size-4" aria-hidden="true" />
              <span>Back to examinations</span>
            </Link>
          </Button></div>
        }
      />

      {routeNotice ? (
        <Alert variant="warning" role="status">
          <AlertTitle>Attempt Finalized</AlertTitle>
          <AlertDescription>{routeNotice}</AlertDescription>
        </Alert>
      ) : null}

      {!result.result_visible ? (
        <Card>
          <CardHeader className="gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-full bg-success-subtle text-success">
                  <FileCheck2 className="size-5" aria-hidden="true" />
                </span>
                <CardTitle as="h2">Submission Recorded</CardTitle>
              </div>
              <Badge variant={isTimerExpired ? "warning" : "secondary"}>
                {isTimerExpired ? (
                  <Timer className="size-3.5" aria-hidden="true" />
                ) : (
                  <CheckCircle2 className="size-3.5" aria-hidden="true" />
                )}
                <span>{formatSubmissionReason(result.submission_reason)}</span>
              </Badge>
            </div>
            <CardDescription>{result.message}</CardDescription>
          </CardHeader>

          <CardContent>
            <dl className="grid grid-cols-1 gap-4 rounded-lg border border-border bg-muted/40 p-4 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Started</dt>
                <dd className="mt-0.5 font-medium tabular-nums text-foreground">
                  <time dateTime={result.started_at}>
                    {formatDateTime(result.started_at)}
                  </time>
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Submitted</dt>
                <dd className="mt-0.5 font-medium tabular-nums text-foreground">
                  {result.submitted_at ? (
                    <time dateTime={result.submitted_at}>
                      {formatDateTime(result.submitted_at)}
                    </time>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
              <div>
                <dt className="text-xs font-medium text-muted-foreground">Questions</dt>
                <dd className="mt-0.5 font-medium tabular-nums text-foreground">
                  {result.total_questions}
                </dd>
              </div>
            </dl>
          </CardContent>
        </Card>
      ) : (
        <div className="student-result-grid"><div className="space-y-6">
          <div className="student-card student-result-hero">
            <div className="student-score-ring" style={{ background: `conic-gradient(${result.passed ? "#0f7a4a" : "#b8340a"} ${Math.max(0, Math.min(100, Number(result.percentage)))}%, #f0eef3 0)` }} role="img" aria-label={`${formatPercentage(result.percentage)} score`}><span>{formatPercentage(result.percentage)}</span></div>
            <div>{result.passed ? <Badge variant="success"><CheckCircle2 className="size-4" />Passed</Badge> : <Badge variant="destructive"><XCircle className="size-4" />Did not pass</Badge>}<h2>You scored {formatDecimalValue(result.points_earned)} of {formatDecimalValue(result.points_available)} points</h2><p>The pass mark for this examination is {formatDecimalValue(result.pass_mark)}%.</p></div>
          </div>
          <Card>
            <CardHeader className="gap-3 border-b border-border/70 pb-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="space-y-1">
                  <CardTitle as="h2">Graded Score Summary</CardTitle>
                  <CardDescription>
                    Pass mark: {formatDecimalValue(result.pass_mark)}%
                  </CardDescription>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  {result.passed ? (
                    <Badge variant="success">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      <span>Passed</span>
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <XCircle className="size-3.5" aria-hidden="true" />
                      <span>Did not pass</span>
                    </Badge>
                  )}

                  <Badge variant={isTimerExpired ? "warning" : "secondary"}>
                    {isTimerExpired ? (
                      <Timer className="size-3.5" aria-hidden="true" />
                    ) : (
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                    )}
                    <span>{formatSubmissionReason(result.submission_reason)}</span>
                  </Badge>
                </div>
              </div>
            </CardHeader>

            <CardContent className="space-y-5 pt-5">
              <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <div className="rounded-lg border border-border bg-muted/40 p-4">
                  <dt className="text-xs font-medium text-muted-foreground">Percentage</dt>
                  <dd className="mt-1 text-2xl font-bold tabular-nums text-foreground">
                    {formatPercentage(result.percentage)}
                  </dd>
                </div>

                <div className="rounded-lg border border-border bg-muted/40 p-4">
                  <dt className="text-xs font-medium text-muted-foreground">Points Score</dt>
                  <dd className="mt-1 text-2xl font-bold tabular-nums text-foreground">
                    {formatDecimalValue(result.points_earned)} /{" "}
                    {formatDecimalValue(result.points_available)}
                  </dd>
                </div>

                <div className="rounded-lg border border-border bg-muted/40 p-4">
                  <dt className="text-xs font-medium text-muted-foreground">Correct / Incorrect</dt>
                  <dd className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                    {result.correct_answers} correct · {result.incorrect_answers} incorrect
                  </dd>
                </div>

                <div className="rounded-lg border border-border bg-muted/40 p-4">
                  <dt className="text-xs font-medium text-muted-foreground">Unanswered</dt>
                  <dd className="mt-1 text-lg font-semibold tabular-nums text-foreground">
                    {result.unanswered_questions} of {result.total_questions}
                  </dd>
                </div>
              </dl>

              <dl className="grid grid-cols-1 gap-3 border-t border-border pt-4 text-sm sm:grid-cols-3">
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">Started</dt>
                  <dd className="mt-0.5 tabular-nums text-foreground">
                    <time dateTime={result.started_at}>
                      {formatDateTime(result.started_at)}
                    </time>
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">Submitted</dt>
                  <dd className="mt-0.5 tabular-nums text-foreground">
                    {result.submitted_at ? (
                      <time dateTime={result.submitted_at}>
                        {formatDateTime(result.submitted_at)}
                      </time>
                    ) : (
                      "—"
                    )}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs font-medium text-muted-foreground">
                    Submission method
                  </dt>
                  <dd className="mt-0.5 text-foreground">
                    {formatSubmissionReason(result.submission_reason)}
                  </dd>
                </div>
              </dl>
            </CardContent>
          </Card>

          <div className="student-card"><div className="student-card-heading"><h2>Answer breakdown</h2></div><div className="student-breakdown" role="img" aria-label={`${result.correct_answers} correct, ${result.incorrect_answers} incorrect, ${result.unanswered_questions} unanswered`}><span style={{ width: `${result.total_questions ? result.correct_answers / result.total_questions * 100 : 0}%`, background: "#0f7a4a" }} /><span style={{ width: `${result.total_questions ? result.incorrect_answers / result.total_questions * 100 : 0}%`, background: "#b8340a" }} /></div></div>

          {result.show_correct_answers &&
          result.question_review &&
          result.question_review.length > 0 ? (
            <section aria-labelledby="question-review-heading" className="space-y-4">
              <div className="space-y-1">
                <h2
                  id="question-review-heading"
                  className="text-lg font-semibold tracking-tight text-foreground sm:text-xl"
                >
                  Question Review
                </h2>
                <p className="text-sm text-muted-foreground">
                  Review your selected answers alongside the correct answers.
                </p>
              </div>

              <div className="space-y-4">
                {result.question_review.map((item, idx) => (
                  <ResultReviewCard key={item.question_id} item={item} index={idx} />
                ))}
              </div>
            </section>
          ) : !result.show_correct_answers ? (
            <Alert variant="default">
              <div className="flex items-start gap-2.5">
                <Info className="mt-0.5 size-5 shrink-0 text-muted-foreground" aria-hidden="true" />
                <div>
                  <AlertTitle>Question review unavailable</AlertTitle>
                  <AlertDescription>
                    Correct answers and question review are not shown for this examination.
                  </AlertDescription>
                </div>
              </div>
            </Alert>
          ) : null}
        </div><aside className="student-card student-details"><div className="student-card-heading"><h2>Sitting details</h2></div><dl><div className="student-detail-row"><dt>Started</dt><dd>{formatDateTime(result.started_at)}</dd></div><div className="student-detail-row"><dt>Submitted</dt><dd>{result.submitted_at ? formatDateTime(result.submitted_at) : "—"}</dd></div><div className="student-detail-row"><dt>Submission</dt><dd>{formatSubmissionReason(result.submission_reason)}</dd></div><div className="student-detail-row"><dt>Questions</dt><dd>{result.total_questions}</dd></div></dl></aside></div>
      )}
    </div>
  );
}
