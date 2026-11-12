import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "@/lib/utils";

const alertVariants = cva(
  "min-w-0 break-words rounded-lg border p-4 text-sm leading-relaxed",
  {
    variants: {
      variant: {
        default: "border-border bg-card text-card-foreground",
        warning: "border-warning-border bg-warning-subtle text-warning",
        destructive:
          "border-destructive-border bg-destructive-subtle text-destructive",
        success: "border-success-border bg-success-subtle text-success",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  },
);

export interface AlertProps
  extends HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof alertVariants> {}

export function Alert({ className, variant, ...props }: AlertProps) {
  return <div className={cn(alertVariants({ variant }), className)} {...props} />;
}

export function AlertTitle({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("font-semibold leading-snug tracking-tight", className)}
      {...props}
    />
  );
}

export function AlertDescription({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-1 min-w-0 text-sm", className)} {...props} />;
}
