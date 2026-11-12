import { CheckCircle2, MinusCircle, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { formatDecimalValue } from "@/features/student/formatters";
import { cn } from "@/lib/utils";
import type { AttemptQuestionReviewItem } from "@/types/studentExam";

export interface ResultReviewCardProps {
  item: AttemptQuestionReviewItem;
  index: number;
}

export function ResultReviewCard({ item, index }: ResultReviewCardProps) {
  const isUnanswered = item.selected_option_id === null;

  return (
    <Card>
      <CardHeader className="flex-row flex-wrap items-start justify-between gap-3 border-b border-border/70 pb-4">
        <div className="min-w-0 flex-1 space-y-1">
          <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground tabular-nums">
            Question {index + 1}
          </p>
          <CardTitle as="h3" className="text-base leading-relaxed sm:text-lg">
            {item.question_text}
          </CardTitle>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Badge variant="outline" className="tabular-nums">
            {formatDecimalValue(item.points_earned)} /{" "}
            {formatDecimalValue(item.points_available)} pts
          </Badge>

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
      </CardHeader>

      <CardContent className="pt-4">
        <div className="grid gap-2.5">
          {item.options.map((option) => {
            const isSelected = option.id === item.selected_option_id;
            const isCorrectOption = option.is_correct;

            return (
              <div
                key={option.id}
                className={cn(
                  "flex min-h-12 flex-wrap items-start gap-3 rounded-lg border px-3.5 py-3 text-sm",
                  isCorrectOption
                    ? "border-success-border bg-success-subtle"
                    : isSelected
                      ? "border-destructive-border bg-destructive-subtle"
                      : "border-border bg-card",
                )}
              >
                <span
                  aria-hidden="true"
                  className={cn(
                    "mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-full border text-xs font-bold",
                    isCorrectOption
                      ? "border-success bg-success text-primary-foreground"
                      : isSelected
                        ? "border-destructive bg-destructive text-primary-foreground"
                        : "border-input bg-card text-foreground",
                  )}
                >
                  {option.label}
                </span>

                <span className="min-w-0 flex-1 break-words pt-1 text-base leading-relaxed text-foreground">
                  {option.option_text}
                </span>

                <div className="flex shrink-0 flex-wrap items-center gap-1.5 pt-1">
                  {isSelected ? (
                    <Badge variant={isCorrectOption ? "success" : "destructive"}>
                      <span>Your answer</span>
                    </Badge>
                  ) : null}
                  {isCorrectOption ? (
                    <Badge variant="success">
                      <CheckCircle2 className="size-3" aria-hidden="true" />
                      <span>Correct answer</span>
                    </Badge>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
