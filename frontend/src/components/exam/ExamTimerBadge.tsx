import { AlertTriangle, Clock } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

export interface ExamTimerBadgeProps {
  expiresAt: string;
  serverNow?: string;
  onExpire?: () => void;
  className?: string;
}

function formatDuration(totalSeconds: number): string {
  const clamped = Math.max(0, Math.floor(totalSeconds));
  const hours = Math.floor(clamped / 3600);
  const minutes = Math.floor((clamped % 3600) / 60);
  const seconds = clamped % 60;

  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function computeRemainingSeconds(expiresAtMs: number, clockOffsetMs: number): number {
  if (!Number.isFinite(expiresAtMs)) {
    return 0;
  }
  const adjustedNow = Date.now() + clockOffsetMs;
  return Math.max(0, Math.ceil((expiresAtMs - adjustedNow) / 1000));
}

export function ExamTimerBadge({
  expiresAt,
  serverNow,
  onExpire,
  className,
}: ExamTimerBadgeProps) {
  const expiresAtMs = Date.parse(expiresAt);
  const clockOffsetRef = useRef<number>(0);
  const onExpireRef = useRef(onExpire);
  const expiredFiredRef = useRef(false);
  const announcedThresholdRef = useRef<"5m" | "1m" | "0" | null>(null);

  const [remainingSeconds, setRemainingSeconds] = useState<number>(() => {
    const serverMs = serverNow ? Date.parse(serverNow) : Number.NaN;
    const initialOffset = Number.isFinite(serverMs) ? serverMs - Date.now() : 0;
    return computeRemainingSeconds(expiresAtMs, initialOffset);
  });
  const [announcement, setAnnouncement] = useState("");
  const [announcementPoliteness, setAnnouncementPoliteness] = useState<"polite" | "assertive">(
    "polite",
  );

  useEffect(() => {
    onExpireRef.current = onExpire;
  }, [onExpire]);

  useEffect(() => {
    const serverMs = serverNow ? Date.parse(serverNow) : Number.NaN;
    clockOffsetRef.current = Number.isFinite(serverMs) ? serverMs - Date.now() : 0;
    const initialRemaining = computeRemainingSeconds(expiresAtMs, clockOffsetRef.current);
    expiredFiredRef.current = initialRemaining === 0;
    announcedThresholdRef.current = initialRemaining === 0 ? "0" : null;
    setRemainingSeconds(initialRemaining);
  }, [expiresAtMs, serverNow]);

  useEffect(() => {
    if (!Number.isFinite(expiresAtMs)) {
      return;
    }

    const syncTimer = () => {
      const next = computeRemainingSeconds(expiresAtMs, clockOffsetRef.current);
      setRemainingSeconds(next);

      if (next === 0) {
        if (announcedThresholdRef.current !== "0") {
          announcedThresholdRef.current = "0";
          setAnnouncementPoliteness("assertive");
          setAnnouncement("Time has expired. Submitting your examination.");
        }
        if (!expiredFiredRef.current) {
          expiredFiredRef.current = true;
          onExpireRef.current?.();
        }
      } else if (next <= 60 && announcedThresholdRef.current !== "1m" && announcedThresholdRef.current !== "0") {
        announcedThresholdRef.current = "1m";
        setAnnouncementPoliteness("assertive");
        setAnnouncement("1 minute remaining.");
      } else if (next <= 300 && announcedThresholdRef.current === null) {
        announcedThresholdRef.current = "5m";
        setAnnouncementPoliteness("polite");
        setAnnouncement("5 minutes remaining.");
      }
    };

    syncTimer();
    const intervalId = window.setInterval(syncTimer, 1000);

    const handleVisibilityOrFocus = () => {
      if (document.visibilityState === "visible") {
        syncTimer();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityOrFocus);
    window.addEventListener("focus", handleVisibilityOrFocus);

    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", handleVisibilityOrFocus);
      window.removeEventListener("focus", handleVisibilityOrFocus);
    };
  }, [expiresAtMs]);

  const isCritical = remainingSeconds <= 60;
  const isWarning = remainingSeconds > 60 && remainingSeconds <= 300;
  const formatted = formatDuration(remainingSeconds);

  return (
    <>
      <div
        role="timer"
        aria-label={`Time remaining: ${formatted}`}
        className={cn(
          "inline-flex min-h-11 shrink-0 items-center gap-2 rounded-full border px-3.5 py-1.5 text-sm font-medium tabular-nums shadow-xs",
          isCritical
            ? "border-destructive-border bg-destructive-subtle font-semibold text-primary"
            : isWarning
              ? "border-warning-border bg-warning-subtle text-warning"
              : "border-border bg-card text-foreground",
          className,
        )}
      >
        {isCritical ? (
          <AlertTriangle className="size-4 shrink-0" aria-hidden="true" />
        ) : (
          <Clock className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
        <span className="hidden xs:inline sm:inline">
          {remainingSeconds === 0 ? "Time expired" : "Time left"}
        </span>
        <span className="font-semibold tracking-tight">{formatted}</span>
      </div>

      <div
        className="visually-hidden"
        aria-live={announcementPoliteness}
        aria-atomic="true"
      >
        {announcement}
      </div>
    </>
  );
}
