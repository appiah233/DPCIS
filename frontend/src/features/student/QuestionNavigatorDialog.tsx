import { CircleDashed, CircleDot } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { QuestionTile } from "@/components/ui/question-tile";
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
          <Badge variant="secondary" className="tabular-nums">
            <CircleDot className="size-3.5" aria-hidden="true" />
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

            return (
              <QuestionTile
                key={question.id}
                questionNumber={index + 1}
                isCurrent={isCurrent}
                isAnswered={isAnswered}
                variant="grid"
                onClick={() => {
                  onSelectIndex(index);
                  onOpenChange(false);
                }}
              />
            );
          })}
        </div>
      </div>
    </Dialog>
  );
}
