import { useEffect, useState } from "react";

import { getNeonAuthToken } from "@/lib/auth";
import { getPublicEnvConfig } from "@/lib/env";

interface Props {
  path: string;
  alt: string;
  className?: string;
  onError?: () => void;
}

/** Fetch private exam imagery with the same bearer token as the JSON API. */
export function AuthenticatedPdfImage({ path, alt, className, onError }: Props) {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
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
      if (!response.ok) { setFailed(true); onError?.(); return; }
      createdUrl = URL.createObjectURL(await response.blob());
      if (!controller.signal.aborted) setObjectUrl(createdUrl);
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
  return (
    <a href={objectUrl} target="_blank" rel="noopener noreferrer" aria-label="Open question image at full size">
      <img src={objectUrl} alt={alt} className={className ?? "h-auto max-w-full"} />
    </a>
  );
}
