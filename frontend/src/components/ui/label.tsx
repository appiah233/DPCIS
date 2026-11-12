import type { LabelHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export function Label({
  className,
  ...props
}: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn(
        "block min-w-0 text-sm font-medium leading-snug text-foreground",
        className,
      )}
      {...props}
    />
  );
}
