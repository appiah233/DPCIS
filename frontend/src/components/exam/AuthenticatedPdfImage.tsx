import { useEffect, useState } from "react";
import { ZoomIn, ZoomOut } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { getNeonAuthToken } from "@/lib/auth";
import { getPublicEnvConfig } from "@/lib/env";

interface Props {
  path: string;
  alt: string;
  className?: string;
  onError?: () => void;
  allowOpenFullSize?: boolean;
  enlargeable?: boolean;
  enlargeTitle?: string;
}

/** Fetch private exam imagery with the same bearer token as the JSON API. */
export function AuthenticatedPdfImage({
  path,
  alt,
  className,
  onError,
  allowOpenFullSize = false,
  enlargeable = false,
  enlargeTitle = "Question image",
}: Props) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [zoomPct, setZoomPct] = useState<number>(100);

  useEffect(() => {
    setFailed(false);
    setObjectUrl(null);
    const controller = new AbortController();
    let createdUrl: string | null = null;
    void (async () => {
      const token = await getNeonAuthToken();
      if (!token || controller.signal.aborted) {
        if (!controller.signal.aborted) { setFailed(true); onError?.(); }
        return;
      }
      const response = await fetch(`${getPublicEnvConfig().apiBaseUrl}${path}`, {
        headers: { Authorization: `Bearer ${token}` },
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      if (!response.ok) { setFailed(true); onError?.(); return; }
      const blob = await response.blob();
      if (controller.signal.aborted) return;
      createdUrl = URL.createObjectURL(blob);
      setObjectUrl(createdUrl);
    })().catch(() => {
      if (!controller.signal.aborted) { setFailed(true); onError?.(); }
    });
    return () => {
      controller.abort();
      if (createdUrl) URL.revokeObjectURL(createdUrl);
    };
  }, [path, onError]);

  if (failed) return <p className="text-sm text-destructive">Question image unavailable.</p>;
  if (!objectUrl) return <p className="text-sm text-muted-foreground">Loading question image…</p>;
  const image = (
    <img
      src={objectUrl}
      alt={alt}
      loading="lazy"
      draggable={false}
      onContextMenu={(event) => event.preventDefault()}
      className={`${className ?? "h-auto max-w-full"} block select-none`}
    />
  );
  if (enlargeable) {
    return (
      <>
        <div className="group relative mb-4">
          <button
            type="button"
            onClick={() => { setZoomPct(100); setLightboxOpen(true); }}
            aria-label={`Enlarge ${enlargeTitle}`}
            className="inline-flex max-w-full cursor-zoom-in flex-col items-start rounded-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            {image}
            <span className="mt-1.5 inline-flex min-h-11 items-center gap-1.5 rounded-md border border-border bg-background px-3 text-xs font-medium text-muted-foreground shadow-sm group-hover:text-foreground">
              <ZoomIn className="size-4" aria-hidden="true" />
              Tap or click image to enlarge
            </span>
          </button>
        </div>

        <Dialog
          open={lightboxOpen}
          onOpenChange={setLightboxOpen}
          title={enlargeTitle}
          className="max-w-5xl"
          footer={
            <div className="flex flex-wrap items-center gap-1.5">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="min-h-11 min-w-11"
                aria-label="Zoom out image"
                disabled={zoomPct <= 75}
                onClick={() => setZoomPct((prev) => Math.max(75, prev - 25))}
              >
                <ZoomOut className="size-4" aria-hidden="true" />
              </Button>
              <span className="min-w-[3.5rem] text-center text-xs font-medium text-muted-foreground">
                {zoomPct}%
              </span>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="min-h-11 min-w-11"
                aria-label="Zoom in image"
                disabled={zoomPct >= 200}
                onClick={() => setZoomPct((prev) => Math.min(200, prev + 25))}
              >
                <ZoomIn className="size-4" aria-hidden="true" />
              </Button>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="min-h-11"
                onClick={() => setZoomPct(100)}
              >
                Fit
              </Button>
            </div>
          }
        >
          <div className="max-h-[calc(100dvh-13rem)] overflow-auto rounded-lg border border-border bg-white p-2">
            <img
              src={objectUrl}
              alt={alt}
              draggable={false}
              onContextMenu={(event) => event.preventDefault()}
              style={zoomPct === 100 ? undefined : { width: `${zoomPct}%`, maxWidth: "none" }}
              className={
                zoomPct === 100
                  ? "mx-auto block h-auto max-h-[calc(100dvh-14rem)] w-auto max-w-full select-none object-contain"
                  : "mx-auto block h-auto select-none"
              }
            />
          </div>
        </Dialog>
      </>
    );
  }
  if (allowOpenFullSize) {
    return (
      <a
        href={objectUrl}
        target="_blank"
        rel="noopener noreferrer"
        aria-label="Open question image at full size"
      >
        {image}
      </a>
    );
  }
  return image;
}
