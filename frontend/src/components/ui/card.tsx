import type { HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

type CardElement = "article" | "section" | "div";
type CardTitleElement = "h2" | "h3" | "h4" | "div";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: CardElement;
}

export function Card({ as = "article", className, ...props }: CardProps) {
  const Comp = as;
  return (
    <Comp
      className={cn(
        "foundation-card flex min-w-0 flex-col rounded-lg border border-border bg-card text-card-foreground shadow-xs",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("flex min-w-0 flex-col flex-wrap gap-1.5 p-5 sm:p-6", className)}
      {...props}
    />
  );
}

export interface CardTitleProps extends HTMLAttributes<HTMLElement> {
  as?: CardTitleElement;
}

export function CardTitle({
  as = "h2",
  className,
  ...props
}: CardTitleProps) {
  const Comp = as;
  return (
    <Comp
      className={cn(
        "min-w-0 break-words text-lg font-semibold leading-snug tracking-tight text-foreground",
        className,
      )}
      {...props}
    />
  );
}

export function CardDescription({
  className,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p
      className={cn("min-w-0 text-sm leading-relaxed text-muted-foreground", className)}
      {...props}
    />
  );
}

export function CardContent({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("min-w-0 flex-1 px-5 pb-5 sm:px-6 sm:pb-6", className)} {...props} />
  );
}

export function CardFooter({
  className,
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <footer
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-3 border-t border-border px-5 py-4 sm:px-6",
        className,
      )}
      {...props}
    />
  );
}

export interface StatCardProps extends HTMLAttributes<HTMLElement> {
  label: string;
  value: ReactNode;
  sublabel?: ReactNode;
  icon?: ReactNode;
  tone?: "default" | "accent" | "success" | "warning" | "danger";
}

const statToneClasses: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-foreground",
  accent: "text-primary",
  success: "text-success",
  warning: "text-warning",
  danger: "text-destructive",
};

export function StatCard({
  label,
  value,
  sublabel,
  icon,
  tone = "default",
  className,
  ...props
}: StatCardProps) {
  return (
    <Card
      as="article"
      className={cn("justify-between p-5", className)}
      {...props}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </p>
        {icon ? (
          <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
            {icon}
          </span>
        ) : null}
      </div>
      <div className="mt-2 space-y-1">
        <p
          className={cn(
            "text-2xl font-bold tracking-tight tabular-nums sm:text-3xl",
            statToneClasses[tone],
          )}
        >
          {value}
        </p>
        {sublabel ? (
          <p className="text-xs text-muted-foreground">{sublabel}</p>
        ) : null}
      </div>
    </Card>
  );
}
