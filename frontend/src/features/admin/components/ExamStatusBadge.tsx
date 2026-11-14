import type { ExamStatus } from "@/types/adminExam";

export interface ExamStatusBadgeProps {
  status: ExamStatus | string;
}

export function ExamStatusBadge({ status }: ExamStatusBadgeProps) {
  if (status === "PUBLISHED") {
    return (
      <span className="admin-pill ok">
        <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="m5 12 5 5 9-10" />
        </svg>
        <span>Published</span>
      </span>
    );
  }

  if (status === "CLOSED") {
    return (
      <span className="admin-pill nt">
        <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="9" />
          <path d="M12 7v5l3 2" />
        </svg>
        <span>Closed</span>
      </span>
    );
  }

  return (
    <span className="admin-pill wn">
      <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
        <path d="M4 20h4L19 9l-4-4L4 16z" />
      </svg>
      <span>Draft</span>
    </span>
  );
}
