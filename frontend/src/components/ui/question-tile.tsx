import { Check, CircleDashed, Flag } from "lucide-react";
import type { ButtonHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface QuestionTileProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  questionNumber: number;
  isCurrent?: boolean;
  isAnswered?: boolean;
  isFlagged?: boolean;
  variant?: "grid" | "row";
}

export function QuestionTile({
  questionNumber,
  isCurrent = false,
  isAnswered = false,
  isFlagged = false,
  variant = "grid",
  type = "button",
  className,
  ...props
}: QuestionTileProps) {
  const statusText = isAnswered ? "Answered" : "Unanswered";

  if (variant === "row") {
    return (
      <button
        type={type}
        aria-current={isCurrent ? "step" : undefined}
        aria-label={`Question ${questionNumber}, ${statusText}${isFlagged ? ", Flagged" : ""}${isCurrent ? ", Current question" : ""}`}
        className={cn(
          "flex min-h-11 w-full cursor-pointer items-center justify-between gap-2.5 rounded-md border px-3 py-2 text-left text-sm font-medium transition-colors",
          isCurrent
            ? "border-primary bg-accent font-semibold text-accent-foreground ring-2 ring-primary/20"
            : isAnswered
              ? "border-selected-border/35 bg-selected-bg text-foreground hover:bg-muted"
              : "border-border bg-card text-foreground hover:bg-muted",
          className,
        )}
        {...props}
      >
        <span className="flex items-center gap-2.5 tabular-nums">
          <span
            aria-hidden="true"
            className={cn(
              "inline-flex size-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold",
              isAnswered
                ? "bg-selected-badge-bg text-selected-badge-fg"
                : "border border-border-strong bg-card text-muted-foreground",
            )}
          >
            {isAnswered ? <Check className="size-3" /> : questionNumber}
          </span>
          <span>Question {questionNumber}</span>
        </span>

        <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {isFlagged ? <Flag className="size-3.5 text-warning" aria-hidden="true" /> : null}
          <span>{isCurrent ? "Current" : statusText}</span>
        </span>
      </button>
    );
  }

  return (
    <button
      type={type}
      aria-current={isCurrent ? "step" : undefined}
      aria-label={`Question ${questionNumber}, ${statusText}${isFlagged ? ", Flagged" : ""}${isCurrent ? ", Current question" : ""}`}
      className={cn(
        "flex min-h-11 cursor-pointer flex-col items-start justify-center gap-0.5 rounded-lg border px-3 py-2 text-left transition-colors",
        isCurrent
          ? "border-primary bg-accent text-accent-foreground ring-2 ring-primary/25"
          : isAnswered
            ? "border-selected-border/40 bg-selected-bg text-foreground hover:bg-muted"
            : "border-border bg-card text-foreground hover:bg-muted",
        className,
      )}
      {...props}
    >
      <span className="flex w-full items-center justify-between gap-1.5 text-sm font-semibold tabular-nums">
        <span>Q{questionNumber}</span>
        {isFlagged ? (
          <Flag className="size-3.5 shrink-0 text-warning" aria-hidden="true" />
        ) : isAnswered ? (
          <Check className="size-3.5 shrink-0 text-selected-border" aria-hidden="true" />
        ) : (
          <CircleDashed className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
      </span>
      <span className="text-xs font-medium text-muted-foreground">
        {isCurrent ? "Current" : statusText}
      </span>
    </button>
  );
}
