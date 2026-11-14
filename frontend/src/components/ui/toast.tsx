import { CheckCircle2, Info, TriangleAlert, X } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

export type ToastVariant = "default" | "success" | "warning" | "destructive";

export interface ToastItem {
  id: string;
  title: string;
  description?: string;
  variant?: ToastVariant;
}

interface ToastContextValue {
  toasts: readonly ToastItem[];
  pushToast: (toast: Omit<ToastItem, "id">) => void;
  dismissToast: (id: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const dismissToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const pushToast = useCallback(
    (toast: Omit<ToastItem, "id">) => {
      const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
      setToasts((prev) => [...prev, { ...toast, id }]);
      window.setTimeout(() => {
        dismissToast(id);
      }, 4500);
    },
    [dismissToast],
  );

  return (
    <ToastContext.Provider value={{ toasts, pushToast, dismissToast }}>
      {children}
      <ToastViewport toasts={toasts} onDismiss={dismissToast} />
    </ToastContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    throw new Error("useToast must be used within a ToastProvider");
  }
  return ctx;
}

export function ToastViewport({
  toasts,
  onDismiss,
}: {
  toasts: readonly ToastItem[];
  onDismiss: (id: string) => void;
}) {
  if (toasts.length === 0) {
    return null;
  }

  return (
    <div
      role="region"
      aria-label="Notifications"
      aria-live="polite"
      className="fixed right-4 bottom-4 z-50 flex w-full max-w-sm flex-col gap-2"
    >
      {toasts.map((item) => {
        const variant = item.variant ?? "default";
        return (
          <div
            key={item.id}
            role={variant === "destructive" ? "alert" : "status"}
            className={cn(
              "flex items-start justify-between gap-3 rounded-lg border p-4 text-sm shadow-md",
              variant === "success" && "border-success-border bg-success-subtle text-success",
              variant === "warning" && "border-warning-border bg-warning-subtle text-warning",
              variant === "destructive" &&
                "border-destructive-border bg-destructive-subtle text-destructive",
              variant === "default" && "border-border bg-card text-foreground",
            )}
          >
            <div className="flex items-start gap-2.5">
              {variant === "success" ? (
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              ) : variant === "warning" || variant === "destructive" ? (
                <TriangleAlert className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              ) : (
                <Info className="mt-0.5 size-4 shrink-0 text-info" aria-hidden="true" />
              )}
              <div className="space-y-0.5">
                <p className="font-semibold leading-snug">{item.title}</p>
                {item.description ? (
                  <p className="text-xs opacity-90">{item.description}</p>
                ) : null}
              </div>
            </div>

            <button
              type="button"
              aria-label="Dismiss notification"
              onClick={() => onDismiss(item.id)}
              className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md hover:bg-muted"
            >
              <X className="size-3.5" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}
