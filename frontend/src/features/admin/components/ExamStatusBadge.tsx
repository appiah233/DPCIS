import { CheckCircle2, Lock, Pencil } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type { ExamStatus } from "@/types/adminExam";

export interface ExamStatusBadgeProps {
  status: ExamStatus | string;
}

export function ExamStatusBadge({ status }: ExamStatusBadgeProps) {
  if (status === "PUBLISHED") {
    return (
      <Badge variant="success">
        <CheckCircle2 className="size-3.5" aria-hidden="true" />
        <span>Published</span>
      </Badge>
    );
  }

  if (status === "CLOSED") {
    return (
      <Badge variant="secondary">
        <Lock className="size-3.5" aria-hidden="true" />
        <span>Closed</span>
      </Badge>
    );
  }

  return (
    <Badge variant="warning">
      <Pencil className="size-3.5" aria-hidden="true" />
      <span>Draft</span>
    </Badge>
  );
}
