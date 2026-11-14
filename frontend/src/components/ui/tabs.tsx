import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";

import { cn } from "@/lib/utils";

export interface TabsProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
}

export function Tabs({ className, children, ...props }: TabsProps) {
  return (
    <div className={cn("space-y-4", className)} {...props}>
      {children}
    </div>
  );
}

export interface TabsListProps extends HTMLAttributes<HTMLDivElement> {
  ariaLabel?: string;
}

export function TabsList({ ariaLabel, className, ...props }: TabsListProps) {
  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      className={cn(
        "inline-flex min-h-11 w-full flex-wrap items-center gap-1.5 border-b border-border pb-2",
        className,
      )}
      {...props}
    />
  );
}

export interface TabsTriggerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  active?: boolean;
}

export function TabsTrigger({
  active = false,
  className,
  type = "button",
  children,
  ...props
}: TabsTriggerProps) {
  return (
    <button
      type={type}
      role="tab"
      aria-selected={active}
      className={cn(
        "inline-flex min-h-10 cursor-pointer items-center justify-center gap-2 rounded-md border px-3.5 py-2 text-sm font-medium transition-colors",
        active
          ? "border-primary/25 bg-accent font-semibold text-accent-foreground"
          : "border-transparent bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export interface TabsContentProps extends HTMLAttributes<HTMLDivElement> {
  active?: boolean;
}

export function TabsContent({
  active = true,
  className,
  children,
  ...props
}: TabsContentProps) {
  if (!active) {
    return null;
  }
  return (
    <div role="tabpanel" className={cn("min-w-0", className)} {...props}>
      {children}
    </div>
  );
}
