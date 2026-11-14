import type { Ref, SelectHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  ref?: Ref<HTMLSelectElement>;
}

export function Select({ className, children, ref, ...props }: SelectProps) {
  return (
    <select
      ref={ref}
      className={cn(
        "flex min-h-11 w-full min-w-0 rounded-md border border-input bg-card px-3.5 py-2.5 text-base text-foreground shadow-2xs transition-colors disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-70 aria-[invalid=true]:border-destructive",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
