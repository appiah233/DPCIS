const DATE_TIME_FORMATTER = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
});

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
