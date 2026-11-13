import type { ReactNode } from "react";

export interface PageHeaderProps {
  eyebrow?: string;
  title: string;
  description: string;
  action?: ReactNode;
}

export function PageHeader({
  eyebrow,
  title,
  description,
  action,
}: PageHeaderProps) {
  return (
    <div className="flex min-w-0 flex-col gap-5 border-b border-border pb-7 pt-2 sm:flex-row sm:items-end sm:justify-between sm:pb-8">
      <div className="min-w-0 flex-1 space-y-3">
        {eyebrow ? (
          <p className="text-xs font-bold uppercase tracking-[0.18em] text-primary">
            {eyebrow}
          </p>
        ) : null}
        <h1
          tabIndex={-1}
          className="break-words text-3xl font-semibold tracking-tight text-foreground outline-none sm:text-4xl lg:text-[2.75rem]"
        >
          {title}
        </h1>
        <p className="max-w-prose text-sm leading-6 text-muted-foreground sm:text-base">
          {description}
        </p>
      </div>
      {action ? <div className="flex shrink-0 flex-wrap gap-2">{action}</div> : null}
    </div>
  );
}
