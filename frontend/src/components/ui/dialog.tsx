import { X } from "lucide-react";
import { useEffect, useId, useRef, type PointerEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  footer?: ReactNode;
  closeOnBackdropClick?: boolean;
  variant?: "modal" | "drawer";
  className?: string;
}

function isPointerOutsideDialog(
  event: PointerEvent<HTMLDialogElement>,
  dialog: HTMLDialogElement,
): boolean {
  const rect = dialog.getBoundingClientRect();
  return (
    event.clientX < rect.left ||
    event.clientX > rect.right ||
    event.clientY < rect.top ||
    event.clientY > rect.bottom
  );
}

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
  closeOnBackdropClick = true,
  variant = "modal",
  className,
}: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const pressedOutsideRef = useRef(false);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    if (open && !dialog.open) {
      triggerRef.current =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
      const initialFocusTarget = dialog.querySelector<HTMLElement>(
        "[data-dialog-initial-focus]:not([disabled])",
      );
      initialFocusTarget?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
      if (triggerRef.current && document.contains(triggerRef.current)) {
        triggerRef.current.focus();
      }
      triggerRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) {
      return;
    }

    const handleClose = () => {
      dialog.returnValue = "";
      onOpenChange(false);
      if (triggerRef.current && document.contains(triggerRef.current)) {
        triggerRef.current.focus();
      }
      triggerRef.current = null;
    };

    const handleCancel = (event: Event) => {
      if (!closeOnBackdropClick) {
        event.preventDefault();
        onOpenChange(false);
      }
    };

    dialog.addEventListener("close", handleClose);
    dialog.addEventListener("cancel", handleCancel);
    return () => {
      dialog.removeEventListener("close", handleClose);
      dialog.removeEventListener("cancel", handleCancel);
    };
  }, [closeOnBackdropClick, onOpenChange]);

  const handlePointerDown = (event: PointerEvent<HTMLDialogElement>) => {
    const dialog = dialogRef.current;
    if (!dialog || !closeOnBackdropClick) {
      pressedOutsideRef.current = false;
      return;
    }
    pressedOutsideRef.current = isPointerOutsideDialog(event, dialog);
  };

  const handlePointerUp = (event: PointerEvent<HTMLDialogElement>) => {
    const dialog = dialogRef.current;
    if (!dialog || !closeOnBackdropClick) {
      return;
    }
    if (pressedOutsideRef.current && isPointerOutsideDialog(event, dialog)) {
      dialog.close();
    }
    pressedOutsideRef.current = false;
  };

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      aria-describedby={description ? descriptionId : undefined}
      onPointerDown={handlePointerDown}
      onPointerUp={handlePointerUp}
      className={cn(
        "exam-dialog",
        variant === "drawer" && "exam-drawer",
        className,
      )}
    >
      <div
        className={cn(
          "flex flex-col",
          variant === "drawer" ? "h-dvh max-h-dvh" : "max-h-[calc(100dvh-2rem)]",
        )}
      >
        <div className="flex items-start justify-between gap-4 border-b border-border px-5 py-4 sm:px-6">
          <div className="min-w-0 space-y-1">
            <h2
              id={titleId}
              className="text-lg font-semibold leading-tight tracking-tight text-foreground"
            >
              {title}
            </h2>
            {description ? (
              <p id={descriptionId} className="text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            ) : null}
          </div>

          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label="Close dialog"
            onClick={() => onOpenChange(false)}
          >
            <X className="size-4" aria-hidden="true" />
          </Button>
        </div>

        {children ? (
          <div
            tabIndex={0}
            role="region"
            aria-label={title}
            className="min-h-0 flex-1 overflow-y-auto px-5 py-5 text-sm text-foreground sm:px-6"
          >
            {children}
          </div>
        ) : null}

        {footer ? (
          <div className="flex flex-col-reverse gap-3 border-t border-border bg-card px-5 py-4 sm:flex-row sm:justify-end sm:px-6">
            {footer}
          </div>
        ) : null}
      </div>
    </dialog>
  );
}

export interface ConfirmDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  confirmVariant?: "default" | "destructive";
  isPending?: boolean;
  onConfirm: () => void;
  children?: ReactNode;
}

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  confirmVariant = "default",
  isPending = false,
  onConfirm,
  children,
}: ConfirmDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title={title}
      description={description}
      closeOnBackdropClick={!isPending}
      footer={
        <>
          <Button
            type="button"
            variant="outline"
            data-dialog-initial-focus="true"
            disabled={isPending}
            onClick={() => onOpenChange(false)}
          >
            {cancelLabel}
          </Button>
          <Button
            type="button"
            variant={confirmVariant}
            isLoading={isPending}
            disabled={isPending}
            onClick={onConfirm}
          >
            {isPending ? "Working..." : confirmLabel}
          </Button>
        </>
      }
    >
      {children}
    </Dialog>
  );
}
