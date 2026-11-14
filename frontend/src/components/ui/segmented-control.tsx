import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface SegmentedControlProps extends HTMLAttributes<HTMLDivElement> {
  ariaLabel: string;
  children: ReactNode;
}

export function SegmentedControl({
  ariaLabel,
  className,
  children,
  ...props
}: SegmentedControlProps) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn("admin-seg", className)}
      {...props}
    >
      {children}
    </div>
  );
}

export interface SegmentedControlItemProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
  count?: number;
}

export function SegmentedControlItem({
  active = false,
  count,
  type = "button",
  className,
  children,
  ...props
}: SegmentedControlItemProps) {
  return (
    <button
      type={type}
      aria-pressed={active}
      className={cn(active && "on", className)}
      {...props}
    >
      <span>{children}</span>
      {typeof count === "number" ? <i>{count}</i> : null}
    </button>
  );
}
