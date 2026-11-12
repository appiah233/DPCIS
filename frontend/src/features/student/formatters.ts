import { ApiClientError } from "@/lib/api";

const DATE_TIME_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

const TECHNICAL_JARGON_PATTERN =
  /\b(fastapi|postgresql|postgres|jwt|rbac|http|server-computed|internal server error|backend|sql|traceback|pydantic|stack\s*trace)\b/i;

function isTechnicalMessage(message: string): boolean {
  return (
    message.startsWith("Backend responded with HTTP ") ||
    message === "Unable to connect to the backend service." ||
    message === "Request timed out or was cancelled." ||
    message === "Failed to fetch" ||
    message.includes("NetworkError") ||
    TECHNICAL_JARGON_PATTERN.test(message)
  );
}

function mapStatusToStudentMessage(
  status: number | undefined,
  code: string | undefined,
  fallback: string,
): string {
  if (code === "ATTEMPT_EXPIRED") {
    return "Examination time has expired. Your attempt has been finalized.";
  }
  if (code === "ATTEMPT_ALREADY_GRADED") {
    return "This examination attempt has already been finalized.";
  }

  switch (status) {
    case 401:
      return "Your sign-in session has expired. Please sign in again to continue.";
    case 403:
      return "You do not have access to this examination.";
    case 404:
      return "This examination or sitting could not be found.";
    case 409:
      return "This examination sitting is no longer accepting changes.";
    case 429:
      return "Too many requests right now. Please wait a moment and try again.";
    default:
      if (status !== undefined && status >= 500) {
        return "The examination service is temporarily unavailable. Please try again in a moment.";
      }
      return fallback;
  }
}

export function formatStudentErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiClientError) {
    const raw = error.message.trim();

    if (raw === "Unable to connect to the backend service.") {
      if (import.meta.env.DEV) {
        console.warn("[Student UI Error]", error);
      }
      return "Unable to reach the examination service. Check your connection and try again.";
    }

    if (raw === "Request timed out or was cancelled.") {
      if (import.meta.env.DEV) {
        console.warn("[Student UI Error]", error);
      }
      return "The request took too long. Check your connection and try again.";
    }

    if (!raw || isTechnicalMessage(raw)) {
      if (import.meta.env.DEV) {
        console.warn("[Student UI Error]", error);
      }
      return mapStatusToStudentMessage(error.status, error.code, fallback);
    }

    return raw;
  }

  if (error instanceof Error) {
    const raw = error.message.trim();
    if (!raw || isTechnicalMessage(raw)) {
      if (import.meta.env.DEV) {
        console.warn("[Student UI Error]", error);
      }
      return fallback;
    }
    return raw;
  }

  if (error !== undefined && error !== null && import.meta.env.DEV) {
    console.warn("[Student UI Error]", error);
  }
  return fallback;
}

export function formatDecimalValue(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "0";
  }
  const numeric = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  return Number.isInteger(numeric) ? String(numeric) : numeric.toFixed(2).replace(/\.?0+$/, "");
}

export function formatPercentage(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const numeric = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return `${String(value)}%`;
  }
  return `${numeric.toFixed(1).replace(/\.0$/, "")}%`;
}

export function formatDateTime(isoString: string | null | undefined): string {
  if (!isoString) {
    return "—";
  }
  const timestamp = Date.parse(isoString);
  if (!Number.isFinite(timestamp)) {
    return isoString;
  }
  return DATE_TIME_FORMATTER.format(new Date(timestamp));
}

export function formatDurationMinutes(minutes: number): string {
  if (!Number.isFinite(minutes) || minutes <= 0) {
    return "0 min";
  }
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours === 0) {
    return `${minutes} ${minutes === 1 ? "min" : "mins"}`;
  }
  if (mins === 0) {
    return `${hours} ${hours === 1 ? "hr" : "hrs"}`;
  }
  return `${hours} ${hours === 1 ? "hr" : "hrs"} ${mins} min`;
}

export function formatSubmissionReason(reason: string | null | undefined): string {
  if (reason === "TIMER_EXPIRED") {
    return "Auto-submitted on timer expiry";
  }
  if (reason === "STUDENT_SUBMITTED") {
    return "Submitted by student";
  }
  return "Completed";
}
