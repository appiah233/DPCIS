import type { HTMLAttributes } from "react";

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
      className={cn("flex min-w-0 flex-col flex-wrap gap-2 p-4 sm:p-6", className)}
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
        "min-w-0 break-words text-lg font-semibold leading-snug tracking-tight",
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
    <div className={cn("min-w-0 flex-1 px-4 pb-4 sm:px-6 sm:pb-6", className)} {...props} />
  );
}

export function CardFooter({
  className,
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <footer
      className={cn(
        "flex min-w-0 flex-wrap items-center gap-3 border-t border-border/70 px-4 py-4 sm:px-6",
        className,
      )}
      {...props}
    />
  );
}
