import type { ButtonHTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface SelectableListItemProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "title"> {
  selected?: boolean;
  title: ReactNode;
  subtitle?: ReactNode;
  trailing?: ReactNode;
}

export function SelectableListItem({
  selected = false,
  title,
  subtitle,
  trailing,
  type = "button",
  className,
  ...props
}: SelectableListItemProps) {
  return (
    <button
      type={type}
      aria-pressed={selected}
      className={cn(
        "flex min-h-16 w-full cursor-pointer items-center justify-between gap-3 rounded-lg border px-4 py-3 text-left transition-colors",
        selected
          ? "border-selected-border bg-selected-bg text-foreground shadow-2xs"
          : "border-border bg-card text-foreground hover:bg-muted",
        className,
      )}
      {...props}
    >
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-foreground">
          {title}
        </span>
        {subtitle ? (
          <span className="mt-1 block text-xs text-muted-foreground">
            {subtitle}
          </span>
        ) : null}
      </span>
      {trailing ? <span className="shrink-0">{trailing}</span> : null}
    </button>
  );
}
