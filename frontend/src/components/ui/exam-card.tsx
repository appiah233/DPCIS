import type { HTMLAttributes, ReactNode } from "react";

import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface ExamCardSpec {
  label: string;
  value: ReactNode;
}

export interface ExamCardProps extends Omit<HTMLAttributes<HTMLElement>, "title"> {
  title: ReactNode;
  description?: ReactNode;
  statusBadge?: ReactNode;
  specs: readonly ExamCardSpec[];
  footerMeta?: ReactNode;
  action?: ReactNode;
}

export function ExamCard({
  title,
  description,
  statusBadge,
  specs,
  footerMeta,
  action,
  className,
  ...props
}: ExamCardProps) {
  return (
    <Card
      as="article"
      className={cn(
        "relative overflow-hidden transition-shadow hover:shadow-md",
        className,
      )}
      {...props}
    >
      <div
        aria-hidden="true"
        className="h-1 w-full bg-primary"
      />
      <CardHeader className="gap-3 pt-5">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <CardTitle as="h3" className="text-lg font-semibold tracking-tight">
            {title}
          </CardTitle>
          {statusBadge}
        </div>
        {description ? <CardDescription>{description}</CardDescription> : null}
      </CardHeader>

      <CardContent>
        <dl className="grid grid-cols-2 gap-x-4 gap-y-4 rounded-lg border border-border bg-muted p-4 text-sm">
          {specs.map((spec) => (
            <div key={spec.label} className="min-w-0">
              <dt className="text-xs font-medium text-muted-foreground">
                {spec.label}
              </dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-foreground">
                {spec.value}
              </dd>
            </div>
          ))}
        </dl>
      </CardContent>

      <CardFooter className="flex-wrap justify-between gap-3 border-t border-border pt-4">
        {footerMeta ? (
          <span className="text-xs text-muted-foreground tabular-nums">
            {footerMeta}
          </span>
        ) : <span />}
        {action}
      </CardFooter>
    </Card>
  );
}
