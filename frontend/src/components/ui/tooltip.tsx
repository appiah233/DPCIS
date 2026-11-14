import { useId, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TooltipProps extends Omit<HTMLAttributes<HTMLSpanElement>, "content"> {
  content: ReactNode;
  children: ReactNode;
}

export function Tooltip({ content, className, children, ...props }: TooltipProps) {
  const tooltipId = useId();
  return (
    <span
      className={cn("group relative inline-flex items-center", className)}
      aria-describedby={tooltipId}
      {...props}
    >
      {children}
      <span
        id={tooltipId}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-40 mb-1.5 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-foreground px-2.5 py-1 text-xs font-medium text-background opacity-0 shadow-sm transition-opacity group-focus-within:visible group-focus-within:opacity-100 group-hover:visible group-hover:opacity-100"
      >
        {content}
      </span>
    </span>
  );
}
