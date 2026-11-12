import { ArrowRight, CheckCircle2, Clock, Lock } from "lucide-react";
import { Link } from "react-router-dom";

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
  formatDecimalValue,
  formatDurationMinutes,
} from "@/features/student/formatters";
import type { ExamStudentOut } from "@/types/studentExam";

export interface StudentExamCardProps {
  exam: ExamStudentOut;
}

export function StudentExamCard({ exam }: StudentExamCardProps) {
  const hasActiveAttempt = Boolean(exam.active_attempt_id);
  const attemptsRemaining = Math.max(0, exam.max_attempts - exam.attempts_used);

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle as="h3" className="text-lg">
            {exam.title}
          </CardTitle>

          {hasActiveAttempt ? (
            <Badge variant="accent">
              <Clock className="size-3.5" aria-hidden="true" />
              <span>In progress</span>
            </Badge>
          ) : exam.can_start ? (
            <Badge variant="success">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              <span>Available</span>
            </Badge>
          ) : (
            <Badge variant="secondary">
              <Lock className="size-3.5" aria-hidden="true" />
              <span>Attempts used</span>
            </Badge>
          )}
        </div>

        {exam.description ? (
          <CardDescription>{exam.description}</CardDescription>
        ) : null}
      </CardHeader>

      <CardContent>
        <dl className="grid grid-cols-2 gap-3 rounded-lg border border-border bg-muted/40 p-3.5 text-sm">
          <div className="min-w-0">
            <dt className="text-xs font-medium text-muted-foreground">Duration</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-foreground">
              {formatDurationMinutes(exam.duration_minutes)}
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs font-medium text-muted-foreground">Questions</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-foreground">
              {exam.question_count}
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs font-medium text-muted-foreground">Pass mark</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-foreground">
              {formatDecimalValue(exam.pass_mark)}%
            </dd>
          </div>
          <div className="min-w-0">
            <dt className="text-xs font-medium text-muted-foreground">Attempts</dt>
            <dd className="mt-0.5 font-semibold tabular-nums text-foreground">
              {exam.attempts_used} / {exam.max_attempts}
            </dd>
          </div>
        </dl>
      </CardContent>

      <CardFooter className="justify-between">
        <span className="text-xs text-muted-foreground tabular-nums">
          {hasActiveAttempt
            ? "Sitting in progress — ready to continue"
            : attemptsRemaining > 0
              ? `${attemptsRemaining} ${attemptsRemaining === 1 ? "attempt" : "attempts"} remaining`
              : "No attempts remaining"}
        </span>

        {hasActiveAttempt && exam.active_attempt_id ? (
          <Button asChild variant="default">
            <Link to={`/student/attempts/${encodeURIComponent(exam.active_attempt_id)}`}>
              <span>Resume Examination</span>
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        ) : exam.can_start ? (
          <Button asChild variant="default">
            <Link to={`/student/exams/${encodeURIComponent(exam.id)}`}>
              <span>Start Examination</span>
              <ArrowRight className="size-4" aria-hidden="true" />
            </Link>
          </Button>
        ) : (
          <Button type="button" variant="outline" disabled>
            <span>Max Attempts Reached</span>
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
