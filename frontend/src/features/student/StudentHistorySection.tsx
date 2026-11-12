import {
  ArrowRight,
  CheckCircle2,
  Clock,
  FileClock,
  History,
  Timer,
  XCircle,
} from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ResponsiveTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableRowHead,
} from "@/components/ui/responsive-table";
import { EmptyStatePanel } from "@/components/ui/state-panel";
import {
  formatDateTime,
  formatDecimalValue,
  formatPercentage,
} from "@/features/student/formatters";
import type { StudentAttemptSummary } from "@/types/studentExam";

export interface StudentHistorySectionProps {
  attempts: readonly StudentAttemptSummary[];
}

export function StudentHistorySection({ attempts }: StudentHistorySectionProps) {
  if (attempts.length === 0) {
    return (
      <EmptyStatePanel
        icon={<History className="size-5" aria-hidden="true" />}
        title="No examination attempts yet"
        description="Once you start or submit an examination, your session timeline and available results will appear here."
      />
    );
  }

  return (
    <ResponsiveTable caption="Your examination attempts and graded outcomes" hideCaption>
      <TableHeader>
        <TableRow>
          <TableHead>Examination</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Timestamp</TableHead>
          <TableHead>Score</TableHead>
          <TableHead className="text-right">Action</TableHead>
        </TableRow>
      </TableHeader>

      <TableBody>
        {attempts.map((attempt) => {
          const isInProgress = attempt.status === "IN_PROGRESS";
          const isGraded = attempt.status === "GRADED";
          const isExpiredSubmit = attempt.submission_reason === "TIMER_EXPIRED";

          return (
            <TableRow key={attempt.attempt_id}>
              <TableRowHead>
                <div className="min-w-0 space-y-0.5">
                  <p className="break-words font-semibold text-foreground">
                    {attempt.exam_title}
                  </p>
                  <p className="text-xs font-normal text-muted-foreground tabular-nums">
                    {attempt.total_questions}{" "}
                    {attempt.total_questions === 1 ? "question" : "questions"}
                  </p>
                </div>
              </TableRowHead>

              <TableCell label="Status">
                {isInProgress ? (
                  <Badge variant="accent">
                    <Clock className="size-3.5" aria-hidden="true" />
                    <span>In progress</span>
                  </Badge>
                ) : isExpiredSubmit ? (
                  <Badge variant="warning">
                    <Timer className="size-3.5" aria-hidden="true" />
                    <span>Auto-submitted</span>
                  </Badge>
                ) : (
                  <Badge variant="secondary">
                    <CheckCircle2 className="size-3.5" aria-hidden="true" />
                    <span>Submitted</span>
                  </Badge>
                )}
              </TableCell>

              <TableCell label={attempt.submitted_at ? "Submitted" : "Started"}>
                <time
                  dateTime={attempt.submitted_at ?? attempt.started_at}
                  className="text-sm text-muted-foreground tabular-nums"
                >
                  {formatDateTime(attempt.submitted_at ?? attempt.started_at)}
                </time>
              </TableCell>

              <TableCell label="Score">
                {isInProgress ? (
                  <span className="text-sm text-muted-foreground">In progress</span>
                ) : !attempt.result_visible ? (
                  <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground">
                    <FileClock className="size-4 shrink-0" aria-hidden="true" />
                    <span>Score not released</span>
                  </span>
                ) : (
                  <div className="flex flex-wrap items-center justify-end gap-2 sm:justify-start">
                    <span className="font-semibold tabular-nums text-foreground">
                      {formatDecimalValue(attempt.points_earned)} /{" "}
                      {formatDecimalValue(attempt.points_available)} (
                      {formatPercentage(attempt.percentage)})
                    </span>
                    {attempt.passed === true ? (
                      <Badge variant="success">
                        <CheckCircle2 className="size-3.5" aria-hidden="true" />
                        <span>Passed</span>
                      </Badge>
                    ) : attempt.passed === false ? (
                      <Badge variant="destructive">
                        <XCircle className="size-3.5" aria-hidden="true" />
                        <span>Did not pass</span>
                      </Badge>
                    ) : null}
                  </div>
                )}
              </TableCell>

              <TableCell label="Action" stackOnMobile className="sm:text-right">
                {isInProgress ? (
                  <Button asChild variant="default" size="sm">
                    <Link to={`/student/attempts/${encodeURIComponent(attempt.attempt_id)}`}>
                      <span>Resume Examination</span>
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                  </Button>
                ) : isGraded && attempt.result_visible ? (
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/student/results/${encodeURIComponent(attempt.attempt_id)}`}>
                      <span>View Result</span>
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                  </Button>
                ) : (
                  <Button asChild variant="outline" size="sm">
                    <Link to={`/student/results/${encodeURIComponent(attempt.attempt_id)}`}>
                      <span>View Confirmation</span>
                      <ArrowRight className="size-4" aria-hidden="true" />
                    </Link>
                  </Button>
                )}
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </ResponsiveTable>
  );
}
