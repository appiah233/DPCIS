import { ArrowRight, CheckCircle2, Clock, Lock } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ExamCard } from "@/components/ui/exam-card";
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

  const statusBadge = hasActiveAttempt ? (
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
  );

  const footerMeta = hasActiveAttempt
    ? "Sitting in progress — ready to continue"
    : attemptsRemaining > 0
      ? `${attemptsRemaining} ${attemptsRemaining === 1 ? "attempt" : "attempts"} remaining`
      : "No attempts remaining";

  const action =
    hasActiveAttempt && exam.active_attempt_id ? (
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
    );

  return (
    <ExamCard
      title={exam.title}
      description={exam.description}
      statusBadge={statusBadge}
      specs={[
        { label: "Duration", value: formatDurationMinutes(exam.duration_minutes) },
        { label: "Questions", value: exam.question_count },
        { label: "Pass mark", value: `${formatDecimalValue(exam.pass_mark)}%` },
        { label: "Attempts", value: `${exam.attempts_used} / ${exam.max_attempts}` },
      ]}
      footerMeta={footerMeta}
      action={action}
    />
  );
}
