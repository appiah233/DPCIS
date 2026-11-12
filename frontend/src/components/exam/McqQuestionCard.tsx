import { ArrowLeft, ArrowRight, Check, Send } from "lucide-react";
import { useId, type RefObject } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface McqOptionItem {
  optionId: string;
  label: "A" | "B" | "C" | "D";
  optionText: string;
}

export interface McqQuestionCardProps {
  questionNumber: number;
  totalQuestions: number;
  questionText: string;
  points?: string | number;
  options: readonly McqOptionItem[];
  selectedOptionId: string | null;
  onSelectOption: (optionId: string) => void;
  disabled?: boolean;
  onPrevious?: () => void;
  onNext?: () => void;
  canGoPrevious?: boolean;
  canGoNext?: boolean;
  onRequestSubmit?: () => void;
  isSubmitting?: boolean;
  submitLabel?: string;
  headingRef?: RefObject<HTMLHeadingElement | null>;
  className?: string;
}

export function McqQuestionCard({
  questionNumber,
  totalQuestions,
  questionText,
  points,
  options,
  selectedOptionId,
  onSelectOption,
  disabled = false,
  onPrevious,
  onNext,
  canGoPrevious = false,
  canGoNext = false,
  onRequestSubmit,
  isSubmitting = false,
  submitLabel = "Submit exam",
  headingRef,
  className,
}: McqQuestionCardProps) {
  const radioGroupName = useId();
  const pointsNumeric = typeof points === "string" ? Number.parseFloat(points) : points;
  const formattedPoints =
    points !== undefined && Number.isFinite(pointsNumeric)
      ? `${pointsNumeric} ${pointsNumeric === 1 ? "pt" : "pts"}`
      : null;

  return (
    <Card className={cn("overflow-visible", className)}>
      <CardHeader className="flex-row items-center justify-between gap-2 border-b border-border/70 pb-4">
        <h2
          ref={headingRef}
          tabIndex={-1}
          className="text-xs font-semibold uppercase tracking-wider text-primary outline-none"
        >
          Question {questionNumber} of {totalQuestions}
        </h2>
        {formattedPoints ? <Badge variant="outline">{formattedPoints}</Badge> : null}
      </CardHeader>

      <CardContent className="pt-5 sm:pt-6">
        <fieldset className="m-0 min-w-0 border-0 p-0">
          <legend className="mb-5 block w-full break-words p-0 text-lg font-semibold leading-relaxed text-foreground sm:text-xl">
            {questionText}
          </legend>

          <div className="grid gap-3">
            {options.map((option) => {
              const optionIdAttr = `${radioGroupName}-${option.optionId}`;
              const isSelected = selectedOptionId === option.optionId;

              return (
                <label
                  key={option.optionId}
                  htmlFor={optionIdAttr}
                  data-selected={isSelected ? "true" : "false"}
                  className={cn(
                    "mcq-option-card group relative flex min-h-14 cursor-pointer items-start gap-3.5 rounded-xl border bg-card px-4 py-3.5 text-left",
                    isSelected
                      ? "border-primary bg-accent"
                      : "border-input/80 hover:border-primary/70 hover:bg-muted/50",
                    disabled && "cursor-not-allowed opacity-70",
                  )}
                >
                  <input
                    id={optionIdAttr}
                    type="radio"
                    name={radioGroupName}
                    value={option.optionId}
                    checked={isSelected}
                    disabled={disabled}
                    onChange={() => onSelectOption(option.optionId)}
                    className="visually-hidden"
                  />

                  <span
                    aria-hidden="true"
                    className={cn(
                      "mt-0.5 inline-flex size-9 shrink-0 items-center justify-center rounded-full border text-sm font-bold transition-colors",
                      isSelected
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-input bg-card text-foreground group-hover:border-primary group-hover:text-primary",
                    )}
                  >
                    {option.label}
                  </span>

                  <span className="min-w-0 flex-1 break-words pt-1 text-base leading-relaxed text-foreground">
                    {option.optionText}
                  </span>

                  {isSelected ? (
                    <span
                      aria-hidden="true"
                      className="mt-1.5 inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-primary"
                    >
                      <Check className="size-4" />
                      <span className="hidden sm:inline">Selected</span>
                    </span>
                  ) : null}
                </label>
              );
            })}
          </div>
        </fieldset>
      </CardContent>

      <CardFooter className="justify-between rounded-b-lg bg-card pb-[max(1rem,env(safe-area-inset-bottom))]">
        <Button
          type="button"
          variant="outline"
          disabled={!canGoPrevious || disabled || isSubmitting}
          onClick={onPrevious}
        >
          <ArrowLeft className="size-4" aria-hidden="true" />
          <span>Previous</span>
        </Button>

        <div className="flex flex-1 flex-wrap items-center justify-end gap-2.5 sm:flex-initial">
          {canGoNext && onNext ? (
            <>
              {onRequestSubmit ? (
                <Button
                  type="button"
                  variant="outline"
                  disabled={disabled || isSubmitting}
                  onClick={onRequestSubmit}
                >
                  <Send className="size-4" aria-hidden="true" />
                  <span>{submitLabel}</span>
                </Button>
              ) : null}
              <Button
                type="button"
                variant="default"
                disabled={disabled || isSubmitting}
                onClick={onNext}
              >
                <span>Next</span>
                <ArrowRight className="size-4" aria-hidden="true" />
              </Button>
            </>
          ) : onRequestSubmit ? (
            <Button
              type="button"
              variant="default"
              disabled={disabled || isSubmitting}
              onClick={onRequestSubmit}
            >
              <Send className="size-4" aria-hidden="true" />
              <span>{isSubmitting ? "Submitting..." : submitLabel}</span>
            </Button>
          ) : null}
        </div>
      </CardFooter>
    </Card>
  );
}
