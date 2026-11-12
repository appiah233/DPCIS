import { CheckCircle2, CircleDashed } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { AttemptQuestionDelivery } from "@/types/studentExam";

export interface QuestionNavigatorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  questions: readonly AttemptQuestionDelivery[];
  answers: Readonly<Record<string, string | null>>;
  currentIndex: number;
  onSelectIndex: (index: number) => void;
}

export function QuestionNavigatorDialog({
  open,
  onOpenChange,
  questions,
  answers,
  currentIndex,
  onSelectIndex,
}: QuestionNavigatorDialogProps) {
  const answeredCount = questions.reduce((count, question) => {
    const selected = answers[question.id];
    return selected ? count + 1 : count;
  }, 0);
  const unansweredCount = Math.max(0, questions.length - answeredCount);

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Question Navigator"
      description="Select any question to jump directly to it. Saved answers remain preserved."
      footer={
        <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
          Close
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="success" className="tabular-nums">
            <CheckCircle2 className="size-3.5" aria-hidden="true" />
            <span>{answeredCount} Answered</span>
          </Badge>
          <Badge variant="secondary" className="tabular-nums">
            <CircleDashed className="size-3.5" aria-hidden="true" />
            <span>{unansweredCount} Unanswered</span>
          </Badge>
        </div>

        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
          {questions.map((question, index) => {
            const isCurrent = index === currentIndex;
            const isAnswered = Boolean(answers[question.id]);
            const statusText = isAnswered ? "Answered" : "Unanswered";

            return (
              <button
                key={question.id}
                type="button"
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`Question ${index + 1}, ${statusText}${isCurrent ? ", Current question" : ""}`}
                onClick={() => {
                  onSelectIndex(index);
                  onOpenChange(false);
                }}
                className={cn(
                  "flex min-h-11 cursor-pointer flex-col items-start justify-center gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors",
                  isCurrent
                    ? "border-primary bg-accent text-accent-foreground ring-2 ring-primary/25"
                    : isAnswered
                      ? "border-success-border bg-success-subtle text-success hover:bg-success-subtle/80"
                      : "border-border bg-card text-foreground hover:bg-muted",
                )}
              >
                <span className="flex w-full items-center justify-between gap-1.5 text-sm font-semibold tabular-nums">
                  <span>Q{index + 1}</span>
                  {isAnswered ? (
                    <CheckCircle2 className="size-3.5 shrink-0" aria-hidden="true" />
                  ) : (
                    <CircleDashed className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                  )}
                </span>
                <span className="text-xs font-medium">
                  {isCurrent ? "Current" : statusText}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </Dialog>
  );
}
