import { ArrowLeft } from "lucide-react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="404"
        title="Page not found"
        description="The requested page does not exist in Examination Hub."
      />
      <Button asChild variant="default">
        <Link to="/">
          <ArrowLeft className="size-4" aria-hidden="true" />
          <span>Return to overview</span>
        </Link>
      </Button>
    </div>
  );
}
