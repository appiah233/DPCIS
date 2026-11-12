import { useId, type HTMLAttributes, type ReactNode, type TdHTMLAttributes, type ThHTMLAttributes } from "react";

import { cn } from "@/lib/utils";

export interface ResponsiveTableProps extends HTMLAttributes<HTMLTableElement> {
  caption: string;
  hideCaption?: boolean;
  wrapperClassName?: string;
  children: ReactNode;
}

export function ResponsiveTable({
  caption,
  hideCaption = false,
  wrapperClassName,
  className,
  children,
  ...props
}: ResponsiveTableProps) {
  const captionId = useId();

  return (
    <div
      tabIndex={0}
      role="region"
      aria-labelledby={captionId}
      className={cn(
        "table-wrapper rounded-lg border border-border bg-card shadow-xs",
        wrapperClassName,
      )}
    >
      <table className={cn("responsive-table text-sm text-foreground", className)} {...props}>
        <caption
          id={captionId}
          className={
            hideCaption
              ? "visually-hidden"
              : "border-b border-border bg-card px-4 py-3 text-left text-sm font-semibold text-foreground"
          }
        >
          {caption}
        </caption>
        {children}
      </table>
    </div>
  );
}

export function TableHeader({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return (
    <thead
      className={cn("border-b border-border bg-muted text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground", className)}
      {...props}
    />
  );
}

export function TableBody({
  className,
  ...props
}: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={cn("divide-y divide-border bg-card", className)} {...props} />;
}

export function TableRow({
  className,
  ...props
}: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cn("transition-colors hover:bg-muted/40", className)} {...props} />;
}

export function TableHead({
  className,
  scope = "col",
  ...props
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope={scope}
      className={cn("whitespace-nowrap px-4 py-3 font-semibold text-foreground", className)}
      {...props}
    />
  );
}

export function TableRowHead({
  className,
  scope = "row",
  ...props
}: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope={scope}
      className={cn("px-4 py-3 text-left font-semibold text-foreground", className)}
      {...props}
    />
  );
}

export interface TableCellProps extends TdHTMLAttributes<HTMLTableCellElement> {
  label: string;
  stackOnMobile?: boolean;
}

export function TableCell({
  label,
  stackOnMobile = false,
  className,
  ...props
}: TableCellProps) {
  return (
    <td
      data-label={label}
      data-cell-stack={stackOnMobile ? "true" : undefined}
      className={cn("px-4 py-3 align-middle text-foreground", className)}
      {...props}
    />
  );
}
