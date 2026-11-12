import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { createAdminExam } from "@/features/admin/adminApi";
import { extractAdminApiError } from "@/features/admin/adminUtils";
import { ExamSettingsForm } from "@/features/admin/components/ExamSettingsForm";
import type { ExamCreate } from "@/types/adminExam";

export function AdminExamNewPage() {
  const navigate = useNavigate();
  const [isCreating, setIsCreating] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const handleCreate = async (payload: ExamCreate) => {
    setIsCreating(true);
    setServerError(null);

    try {
      const created = await createAdminExam(payload);
      navigate(`/admin/exams/${created.id}`, { replace: true });
    } catch (error) {
      setServerError(
        extractAdminApiError(error, "Unable to create draft examination.").message,
      );
      setIsCreating(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Administrator Workspace"
        title="Create New Examination"
        description="Step 1: Define examination timing, pass mark, randomization, and feedback policies. You can bulk-paste MCQ questions immediately on the next screen."
        action={
          <Button asChild variant="outline">
            <Link to="/admin">
              <ArrowLeft className="size-4" aria-hidden="true" />
              <span>Back to Dashboard</span>
            </Link>
          </Button>
        }
      />

      <ExamSettingsForm
        mode="create"
        isSubmitting={isCreating}
        serverError={serverError}
        onSubmit={handleCreate}
      />
    </div>
  );
}
