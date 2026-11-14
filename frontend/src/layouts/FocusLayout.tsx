import { ShieldCheck } from "lucide-react";
import type { ReactNode, RefObject } from "react";
import "@/features/student/student-console.css";

export interface FocusLayoutProps {
  mainRef: RefObject<HTMLElement | null>;
  examTitle?: string;
  examHeaderSlot?: ReactNode;
  children: ReactNode;
}

export function FocusLayout({
  mainRef,
  examTitle,
  examHeaderSlot,
  children,
}: FocusLayoutProps) {
  return (
    <div className="student-console student-focus flex min-h-dvh flex-col bg-background text-foreground">
      <header className="sticky top-0 z-30 border-b border-border bg-card/95 backdrop-blur-xs">
        <div className="flex min-h-16 w-full flex-wrap items-center justify-between gap-3 px-5 py-2 lg:px-10">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="inline-flex size-8 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <ShieldCheck className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0">
              <p className="truncate text-sm font-semibold tracking-tight text-foreground sm:text-base">
                {examTitle ?? "Active Examination"}
              </p>
              <p className="text-xs text-muted-foreground">Timed assessment session</p>
            </div>
          </div>

          {examHeaderSlot ? <div className="shrink-0">{examHeaderSlot}</div> : null}
        </div>
      </header>

      <main
        id="main-content"
        ref={mainRef}
        className="w-full flex-1 px-5 py-5 outline-none lg:px-10 lg:py-6"
      >
        {children}
      </main>
    </div>
  );
}
