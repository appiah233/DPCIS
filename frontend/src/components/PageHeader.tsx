import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface PageHeaderProps {
  breadcrumbs?: ReactNode;
  eyebrow?: string;
  title: string;
  description?: string;
  meta?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function PageHeader({
  breadcrumbs,
  eyebrow,
  title,
  description,
  meta,
  action,
  className,
}: PageHeaderProps) {
  return (
    <header className={cn("admin-ph", className)}>
      <div className="min-w-0">
        {breadcrumbs ? (
          <nav aria-label="Breadcrumb" className="mb-1 text-xs font-medium text-muted-foreground">
            {breadcrumbs}
          </nav>
        ) : null}

        {eyebrow ? <small>{eyebrow}</small> : null}

        <div className="flex flex-wrap items-center gap-2.5">
          <h1>{title}</h1>
          {meta ? <div className="flex flex-wrap items-center gap-2">{meta}</div> : null}
        </div>

        {description ? <p>{description}</p> : null}
      </div>

      {action ? <div className="admin-acts">{action}</div> : null}
    </header>
  );
}
