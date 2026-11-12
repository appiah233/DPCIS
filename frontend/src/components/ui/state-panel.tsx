import { AlertTriangle, Inbox, RotateCcw } from "lucide-react";
import type { ReactNode } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

export interface LoadingStatePanelProps {
  label?: string;
  cards?: number;
  className?: string;
}

export function LoadingStatePanel({
  label = "Loading content...",
  cards = 2,
  className,
}: LoadingStatePanelProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label={label}
      className={cn("space-y-4", className)}
    >
      <span className="visually-hidden">{label}</span>
      <div className="card-grid">
        {Array.from({ length: cards }, (_, index) => (
          <Card key={index}>
            <CardHeader>
              <Skeleton className="h-5 w-2/5" />
              <Skeleton className="h-4 w-4/5" />
            </CardHeader>
            <CardContent className="space-y-2.5">
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-11 w-32" />
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

export interface ErrorStatePanelProps {
  title?: string;
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  action?: ReactNode;
  className?: string;
}

export function ErrorStatePanel({
  title = "Unable to load this section",
  message,
  onRetry,
  retryLabel = "Try again",
  action,
  className,
}: ErrorStatePanelProps) {
  return (
    <Alert variant="destructive" role="alert" className={className}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
          <div className="min-w-0 space-y-1">
            <AlertTitle>{title}</AlertTitle>
            <AlertDescription>{message}</AlertDescription>
          </div>
        </div>
        {onRetry || action ? (
          <div className="flex shrink-0 flex-wrap gap-2">
            {onRetry ? (
              <Button type="button" variant="outline" onClick={onRetry}>
                <RotateCcw className="size-4" aria-hidden="true" />
                <span>{retryLabel}</span>
              </Button>
            ) : null}
            {action}
          </div>
        ) : null}
      </div>
    </Alert>
  );
}

export interface EmptyStatePanelProps {
  title: string;
  description: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyStatePanel({
  title,
  description,
  icon,
  action,
  className,
}: EmptyStatePanelProps) {
  return (
    <Card className={cn("text-center", className)}>
      <CardHeader className="items-center pt-8">
        <span className="inline-flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
          {icon ?? <Inbox className="size-5" aria-hidden="true" />}
        </span>
        <CardTitle as="h2" className="mt-2">
          {title}
        </CardTitle>
        <CardDescription className="max-w-md">{description}</CardDescription>
      </CardHeader>
      {action ? (
        <CardContent className="flex justify-center pb-8">{action}</CardContent>
      ) : null}
    </Card>
  );
}
