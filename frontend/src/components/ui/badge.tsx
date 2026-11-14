import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium leading-5",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        accent: "border-primary/25 bg-accent text-accent-foreground",
        secondary: "border-border bg-muted text-foreground",
        outline: "border-border-strong bg-card text-foreground",
        selected:
          "border-selected-border bg-selected-bg font-semibold text-selected-border",
        info: "border-info-border bg-info-subtle text-info",
        success: "border-success-border bg-success-subtle text-success",
        warning: "border-warning-border bg-warning-subtle text-warning",
        destructive:
          "border-destructive-border bg-destructive-subtle text-destructive",
      },
    },
    defaultVariants: {
      variant: "secondary",
    },
  },
);

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}

export interface StatusPillProps extends BadgeProps {
  dot?: boolean;
  icon?: ReactNode;
}

export function StatusPill({
  variant = "secondary",
  dot = true,
  icon,
  children,
  className,
  ...props
}: StatusPillProps) {
  return (
    <Badge
      variant={variant}
      className={cn("font-semibold tracking-tight", className)}
      {...props}
    >
      {icon ? (
        icon
      ) : dot ? (
        <span
          aria-hidden="true"
          className="size-1.5 shrink-0 rounded-full bg-current"
        />
      ) : null}
      <span>{children}</span>
    </Badge>
  );
}
