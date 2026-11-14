import { Upload } from "lucide-react";
import { useRef, type ChangeEvent, type DragEvent, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface FileDropzoneProps {
  accept?: string;
  disabled?: boolean;
  label: string;
  description?: string;
  actionLabel?: string;
  icon?: ReactNode;
  onFilesSelected: (files: FileList) => void;
  className?: string;
}

export function FileDropzone({
  accept,
  disabled = false,
  label,
  description,
  actionLabel = "Choose file",
  icon,
  onFilesSelected,
  className,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files.length > 0) {
      onFilesSelected(event.target.files);
      event.target.value = "";
    }
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    if (disabled) {
      return;
    }
    if (event.dataTransfer.files && event.dataTransfer.files.length > 0) {
      onFilesSelected(event.dataTransfer.files);
    }
  };

  return (
    <div
      onDragOver={(e) => e.preventDefault()}
      onDrop={handleDrop}
      className={cn(
        "flex flex-col items-start justify-between gap-4 rounded-lg border border-dashed border-border-strong bg-muted/50 p-5 sm:flex-row sm:items-center",
        disabled && "opacity-60",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-lg border border-border bg-card text-muted-foreground">
          {icon ?? <Upload className="size-4" aria-hidden="true" />}
        </span>
        <div className="space-y-0.5">
          <p className="text-sm font-semibold text-foreground">{label}</p>
          {description ? (
            <p className="text-xs text-muted-foreground">{description}</p>
          ) : null}
        </div>
      </div>

      <div>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          disabled={disabled}
          onChange={handleChange}
          className="sr-only"
        />
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          onClick={() => inputRef.current?.click()}
        >
          {actionLabel}
        </Button>
      </div>
    </div>
  );
}
