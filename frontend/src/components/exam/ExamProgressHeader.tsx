import { AlertTriangle, CheckCircle2, LayoutGrid, Loader2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export type AnswerSaveStatus = "idle" | "saving" | "saved" | "error";

export interface ExamProgressHeaderProps {
  currentIndex: number;
  totalQuestions: number;
  answeredCount: number;
  saveStatus?: AnswerSaveStatus;
  saveMessage?: string;
  onOpenQuestionMap?: () => void;
  className?: string;
}

export function ExamProgressHeader({
  currentIndex,
  totalQuestions,
  answeredCount,
  saveStatus = "idle",
  saveMessage,
  onOpenQuestionMap,
  className,
}: ExamProgressHeaderProps) {
  const safeTotal = Math.max(1, totalQuestions);
  const currentNumber = Math.min(safeTotal, Math.max(1, currentIndex + 1));
  const safeAnswered = Math.min(safeTotal, Math.max(0, answeredCount));

  return (
    <section
      aria-label="Examination progress"
      className={cn(
        "rounded-lg border border-border bg-card p-3.5 shadow-xs sm:p-4",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className="text-sm font-semibold tabular-nums text-foreground sm:text-base">
            Question {currentNumber} of {safeTotal}
          </span>
          <Badge variant="secondary" className="tabular-nums">
            {safeAnswered} / {safeTotal} answered
          </Badge>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {saveStatus === "saving" ? (
            <Badge variant="secondary" role="status">
              <Loader2
                className="size-3.5 animate-spin motion-reduce:animate-none"
                aria-hidden="true"
              />
              <span>{saveMessage ?? "Saving..."}</span>
            </Badge>
          ) : saveStatus === "saved" ? (
            <Badge variant="success" role="status">
              <CheckCircle2 className="size-3.5" aria-hidden="true" />
              <span>{saveMessage ?? "Saved"}</span>
            </Badge>
          ) : saveStatus === "error" ? (
            <Badge variant="destructive" role="status">
              <AlertTriangle className="size-3.5" aria-hidden="true" />
              <span>{saveMessage ?? "Save failed"}</span>
            </Badge>
          ) : null}

          {onOpenQuestionMap ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onOpenQuestionMap}
            >
              <LayoutGrid className="size-4" aria-hidden="true" />
              <span>All questions</span>
            </Button>
          ) : null}
        </div>
      </div>

      <progress
        className="exam-progress mt-3"
        max={safeTotal}
        value={safeAnswered}
        aria-label={`${safeAnswered} of ${safeTotal} questions answered`}
      />
    </section>
  );
}
