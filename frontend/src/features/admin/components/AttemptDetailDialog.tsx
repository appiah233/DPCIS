import { CheckCircle2, Clock, MinusCircle, XCircle } from "lucide-react";
import { useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorStatePanel } from "@/components/ui/state-panel";
import { getAdminAttemptDetail } from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  formatDateTime,
  formatDecimal,
  formatSubmissionReason,
} from "@/features/admin/adminUtils";
import { cn } from "@/lib/utils";
import type { AttemptResultOut } from "@/types/adminExam";

export interface AttemptDetailDialogProps {
  attemptId: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AttemptDetailDialog({
  attemptId,
  open,
  onOpenChange,
}: AttemptDetailDialogProps) {
  const [detail, setDetail] = useState<AttemptResultOut | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  useEffect(() => {
    if (!open || !attemptId) {
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage(null);
    setDetail(null);

    getAdminAttemptDetail(attemptId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setDetail(data);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setErrorMessage(
            extractAdminApiError(error, "Unable to load attempt details.").message,
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [attemptId, open, reloadToken]);

  const studentLabel =
    detail?.student_display_name || detail?.student_email || "Student Attempt";

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={detail ? `Attempt Inspection — ${studentLabel}` : "Attempt Inspection"}
      description={
        detail
          ? `${detail.exam_title}${detail.student_email ? ` · ${detail.student_email}` : ""}`
          : "Loading server-graded attempt breakdown."
      }
      footer={
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Close
        </Button>
      }
    >
      {isLoading ? (
        <div className="space-y-4 py-2" role="status" aria-label="Loading attempt details">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-28 w-full" />
        </div>
      ) : errorMessage ? (
        <ErrorStatePanel
          title="Could not load attempt details"
          message={errorMessage}
          onRetry={() => setReloadToken((n) => n + 1)}
        />
      ) : detail ? (
        <div className="space-y-5">
          <div className="rounded-lg border border-border bg-muted/30 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={detail.status === "GRADED" ? "default" : "secondary"}>
                  {detail.status}
                </Badge>
                {detail.status === "GRADED" ? (
                  detail.passed ? (
                    <Badge variant="success">
                      <CheckCircle2 className="size-3.5" aria-hidden="true" />
                      <span>Passed</span>
                    </Badge>
                  ) : (
                    <Badge variant="destructive">
                      <XCircle className="size-3.5" aria-hidden="true" />
                      <span>Failed</span>
                    </Badge>
                  )
                ) : (
                  <Badge variant="warning">
                    <Clock className="size-3.5" aria-hidden="true" />
                    <span>In progress</span>
                  </Badge>
                )}
              </div>

              <span className="text-xs font-medium text-muted-foreground">
                {formatSubmissionReason(detail.submission_reason)}
              </span>
            </div>

            <dl className="mt-3 grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-xs text-muted-foreground">Score</dt>
                <dd className="font-semibold tabular-nums">
                  {detail.status === "GRADED"
                    ? `${formatDecimal(detail.points_earned)} / ${formatDecimal(detail.points_available)}`
                    : "Pending"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Percentage</dt>
                <dd className="font-semibold tabular-nums">
                  {detail.status === "GRADED"
                    ? `${formatDecimal(detail.percentage)}% (Pass ${formatDecimal(detail.pass_mark)}%)`
                    : "—"}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Breakdown</dt>
                <dd className="text-xs font-medium tabular-nums sm:text-sm">
                  {detail.status === "GRADED"
                    ? `${detail.correct_answers} right · ${detail.incorrect_answers} wrong · ${detail.unanswered_questions} skipped`
                    : `${detail.total_questions} questions`}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Started</dt>
                <dd className="text-xs text-foreground">{formatDateTime(detail.started_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Deadline</dt>
                <dd className="text-xs text-foreground">{formatDateTime(detail.expires_at)}</dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Submitted</dt>
                <dd className="text-xs text-foreground">{formatDateTime(detail.submitted_at)}</dd>
              </div>
            </dl>
          </div>

          {detail.question_review === null ? (
            <Alert variant="default">
              <AlertTitle>Question breakdown unavailable yet</AlertTitle>
              <AlertDescription>
                Per-question grading details are recorded once this attempt is submitted or expires.
              </AlertDescription>
            </Alert>
          ) : detail.question_review.length === 0 ? (
            <Alert variant="default">
              <AlertTitle>No questions recorded</AlertTitle>
              <AlertDescription>
                This attempt contains no frozen question items.
              </AlertDescription>
            </Alert>
          ) : (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-foreground">
                Question Breakdown ({detail.question_review.length})
              </h3>
              <ol className="space-y-3">
                {[...detail.question_review]
                  .sort((a, b) => a.display_order - b.display_order)
                  .map((item, idx) => {
                    const isUnanswered = item.selected_option_id === null;
                    return (
                      <li
                        key={item.question_id}
                        className="rounded-lg border border-border bg-card p-3.5"
                      >
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Question {idx + 1} · {formatDecimal(item.points_earned)} /{" "}
                            {formatDecimal(item.points_available)} pts
                          </p>
                          {item.is_correct ? (
                            <Badge variant="success">
                              <CheckCircle2 className="size-3.5" aria-hidden="true" />
                              <span>Correct</span>
                            </Badge>
                          ) : isUnanswered ? (
                            <Badge variant="secondary">
                              <MinusCircle className="size-3.5" aria-hidden="true" />
                              <span>Unanswered</span>
                            </Badge>
                          ) : (
                            <Badge variant="destructive">
                              <XCircle className="size-3.5" aria-hidden="true" />
                              <span>Incorrect</span>
                            </Badge>
                          )}
                        </div>

                        <p className="mt-2 break-words text-sm font-medium text-foreground">
                          {item.question_text}
                        </p>

                        <ul className="mt-3 space-y-1.5">
                          {item.options.map((option) => {
                            const isSelected = item.selected_option_id === option.id;
                            const isCorrectOpt = option.is_correct;

                            return (
                              <li
                                key={option.id}
                                className={cn(
                                  "flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2 text-xs sm:text-sm",
                                  isCorrectOpt
                                    ? "border-success-border bg-success-subtle text-success"
                                    : isSelected
                                      ? "border-destructive-border bg-destructive-subtle text-destructive"
                                      : "border-border bg-background text-foreground",
                                )}
                              >
                                <span className="min-w-0 flex-1 break-words">
                                  <strong className="mr-1.5">{option.label}.</strong>
                                  {option.option_text}
                                </span>
                                <span className="flex shrink-0 flex-wrap gap-1.5">
                                  {isSelected ? (
                                    <Badge variant={isCorrectOpt ? "success" : "destructive"}>
                                      Selected
                                    </Badge>
                                  ) : null}
                                  {isCorrectOpt ? (
                                    <Badge variant="success">Correct key</Badge>
                                  ) : null}
                                </span>
                              </li>
                            );
                          })}
                        </ul>
                      </li>
                    );
                  })}
              </ol>
            </div>
          )}
        </div>
      ) : null}
    </Dialog>
  );
}
