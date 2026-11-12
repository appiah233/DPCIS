import { ArrowRight, BookOpen, Plus } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { EmptyStatePanel, ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { listAdminExams } from "@/features/admin/adminApi";
import { extractAdminApiError, formatDateTime } from "@/features/admin/adminUtils";
import { ExamStatusBadge } from "@/features/admin/components/ExamStatusBadge";
import type { ExamAdminOut } from "@/types/adminExam";

export function AdminOverviewPage() {
  const [exams, setExams] = useState<ExamAdminOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const retry = useCallback(() => setReload((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    listAdminExams(undefined, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setExams(data);
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setError(extractAdminApiError(cause, "Unable to load your examinations.").message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reload]);

  const snapshot = useMemo(() => {
    const recent = [...exams]
      .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
      .slice(0, 5);
    const published = exams
      .filter((exam) => exam.status === "PUBLISHED")
      .sort((a, b) => Date.parse(b.published_at ?? b.updated_at) - Date.parse(a.published_at ?? a.updated_at))
      .slice(0, 4);
    return {
      total: exams.length,
      draft: exams.filter((exam) => exam.status === "DRAFT").length,
      published: exams.filter((exam) => exam.status === "PUBLISHED").length,
      closed: exams.filter((exam) => exam.status === "CLOSED").length,
      recent,
      current: published,
    };
  }, [exams]);

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Admin Console"
        title="Overview"
        description="A clear view of your examinations and what needs attention."
        action={<Button asChild><Link to="/admin/exams/new"><Plus className="size-4" aria-hidden="true" />Create Examination</Link></Button>}
      />

      {loading ? <LoadingStatePanel label="Loading examination overview..." cards={3} /> : error ? (
        <ErrorStatePanel title="Could not load overview" message={error} onRetry={retry} />
      ) : exams.length === 0 ? (
        <EmptyStatePanel
          icon={<BookOpen className="size-5" aria-hidden="true" />}
          title="Your first examination starts here"
          description="Create a draft, add questions, then publish when it is ready for students."
          action={<Button asChild><Link to="/admin/exams/new">Create Examination</Link></Button>}
        />
      ) : (
        <>
          <section aria-labelledby="overview-counts-heading" className="space-y-3">
            <h2 id="overview-counts-heading" className="text-base font-semibold">Examination snapshot</h2>
            <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-border bg-border sm:grid-cols-4">
              {([
                ["Total", snapshot.total],
                ["Draft", snapshot.draft],
                ["Published", snapshot.published],
                ["Closed", snapshot.closed],
              ] as const).map(([label, value]) => (
                <div key={label} className="bg-card px-4 py-4 sm:px-5">
                  <dt className="text-sm text-muted-foreground">{label}</dt>
                  <dd className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</dd>
                </div>
              ))}
            </dl>
          </section>

          <div className="grid gap-8 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
            <section aria-labelledby="recent-exams-heading" className="min-w-0 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <h2 id="recent-exams-heading" className="text-base font-semibold">Recently updated</h2>
                <Link to="/admin/exams" className="inline-flex min-h-11 items-center gap-1 text-sm font-medium text-primary underline-offset-4 hover:underline">View all <ArrowRight className="size-4" aria-hidden="true" /></Link>
              </div>
              <ul className="divide-y divide-border rounded-xl border border-border bg-card">
                {snapshot.recent.map((exam) => (
                  <li key={exam.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 px-4 py-3 sm:px-5">
                    <div className="min-w-0 flex-1">
                      <Link to={`/admin/exams/${exam.id}`} className="inline-flex min-h-11 items-center break-words font-medium text-foreground underline-offset-4 hover:text-primary hover:underline">{exam.title}</Link>
                      <p className="text-xs text-muted-foreground">Updated {formatDateTime(exam.updated_at)}</p>
                    </div>
                    <ExamStatusBadge status={exam.status} />
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="published-exams-heading" className="min-w-0 space-y-3">
              <h2 id="published-exams-heading" className="flex min-h-11 items-center text-base font-semibold">Available to students</h2>
              {snapshot.current.length === 0 ? (
                <p className="rounded-xl border border-border bg-card px-5 py-5 text-sm text-muted-foreground">No examinations are published yet. Open a draft to finish and publish it.</p>
              ) : (
                <ul className="divide-y divide-border rounded-xl border border-border bg-card">
                  {snapshot.current.map((exam) => (
                    <li key={exam.id} className="px-4 py-3 sm:px-5">
                      <Link to={`/admin/exams/${exam.id}`} className="inline-flex min-h-11 items-center break-words font-medium text-foreground underline-offset-4 hover:text-primary hover:underline">{exam.title}</Link>
                      <p className="text-xs text-muted-foreground">{exam.question_count} questions · {exam.duration_minutes} minutes</p>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
