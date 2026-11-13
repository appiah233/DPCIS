import { ArrowRight, BookOpen, Clock3, FileText, Plus, Radio } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

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
        if (!controller.signal.aborted) setError(extractAdminApiError(cause, "Unable to load your examinations.").message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [reload]);

  const snapshot = useMemo(() => {
    const recent = [...exams].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at)).slice(0, 5);
    const current = exams
      .filter((exam) => exam.status === "PUBLISHED")
      .sort((a, b) => Date.parse(b.published_at ?? b.updated_at) - Date.parse(a.published_at ?? a.updated_at))
      .slice(0, 4);
    return {
      total: exams.length,
      draft: exams.filter((exam) => exam.status === "DRAFT").length,
      published: exams.filter((exam) => exam.status === "PUBLISHED").length,
      closed: exams.filter((exam) => exam.status === "CLOSED").length,
      recent,
      current,
    };
  }, [exams]);

  return (
    <div className="space-y-8 pb-8 sm:space-y-10">
      <section className="portal-hero portal-hero-admin portal-reveal px-6 py-8 sm:px-10 sm:py-10 lg:px-12 lg:py-12" aria-labelledby="admin-overview-title">
        <div className="relative z-10 grid gap-8 lg:grid-cols-[minmax(0,1.4fr)_minmax(280px,0.6fr)] lg:items-end">
          <div>
            <p className="portal-eyebrow">Examination Hub / Admin workspace</p>
            <h1 id="admin-overview-title" className="mt-5 max-w-2xl text-4xl font-semibold tracking-tight text-white sm:text-5xl lg:text-6xl">Make every examination count.</h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-slate-200">Create, publish, and manage assessments from one clear workspace.</p>
            <Button asChild className="mt-8 min-h-12 rounded-xl bg-white px-5 font-semibold text-slate-950 shadow-lg hover:bg-slate-100">
              <Link to="/admin/exams/new"><Plus className="size-4" aria-hidden="true" />Create examination</Link>
            </Button>
          </div>
          <div className="rounded-2xl border border-white/20 bg-white/10 p-5 text-white backdrop-blur-sm sm:p-6">
            <div className="flex items-center gap-3 text-sm font-medium text-slate-200"><Radio className="size-4 text-red-300" aria-hidden="true" />Live overview</div>
            <p className="mt-5 text-5xl font-semibold tabular-nums tracking-tight">{loading ? "—" : snapshot.published}</p>
            <p className="mt-2 text-sm text-slate-200">{snapshot.published === 1 ? "examination available" : "examinations available"} to students</p>
            <Link to="/admin/exams" className="mt-6 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-white underline-offset-4 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white">Manage examinations <ArrowRight className="size-4" aria-hidden="true" /></Link>
          </div>
        </div>
      </section>

      {loading ? <LoadingStatePanel label="Loading examination overview..." cards={3} /> : error ? (
        <ErrorStatePanel title="Could not load overview" message={error} onRetry={retry} />
      ) : exams.length === 0 ? (
        <EmptyStatePanel icon={<BookOpen className="size-5" aria-hidden="true" />} title="Your first examination starts here" description="Create a draft, add questions, then publish when it is ready for students." action={<Button asChild><Link to="/admin/exams/new">Create examination</Link></Button>} />
      ) : (
        <>
          <section aria-labelledby="overview-counts-heading" className="space-y-4 portal-reveal">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">At a glance</p><h2 id="overview-counts-heading" className="mt-1 text-2xl font-semibold tracking-tight text-foreground">Examination snapshot</h2></div>
              <p className="text-sm text-muted-foreground">A current view of your assessment library</p>
            </div>
            <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {([
                ["Total examinations", snapshot.total, BookOpen],
                ["Drafts in progress", snapshot.draft, FileText],
                ["Published", snapshot.published, Radio],
                ["Closed", snapshot.closed, Clock3],
              ] as const).map(([label, value, Icon]) => (
                <div key={label} className="portal-stat p-5 sm:p-6">
                  <dt className="flex items-center justify-between gap-2 text-sm font-medium text-muted-foreground"><span>{label}</span><Icon className="size-5 text-primary" aria-hidden="true" /></dt>
                  <dd className="mt-7 text-4xl font-semibold tabular-nums tracking-tight text-foreground">{value}</dd>
                </div>
              ))}
            </dl>
          </section>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
            <section aria-labelledby="recent-exams-heading" className="portal-panel min-w-0 overflow-hidden">
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-5 py-5 sm:px-6">
                <div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Your library</p><h2 id="recent-exams-heading" className="mt-1 text-xl font-semibold tracking-tight">Recently updated</h2></div>
                <Link to="/admin/exams" className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline">View all <ArrowRight className="size-4" aria-hidden="true" /></Link>
              </div>
              <ul className="divide-y divide-border">
                {snapshot.recent.map((exam) => (
                  <li key={exam.id} className="portal-list-row flex flex-wrap items-center justify-between gap-3 px-5 py-4 sm:px-6">
                    <div className="min-w-0 flex-1"><Link to={`/admin/exams/${exam.id}`} className="inline-flex min-h-11 items-center break-words text-base font-semibold text-foreground underline-offset-4 hover:text-primary hover:underline">{exam.title}</Link><p className="text-xs text-muted-foreground">Updated {formatDateTime(exam.updated_at)}</p></div>
                    <ExamStatusBadge status={exam.status} />
                  </li>
                ))}
              </ul>
            </section>

            <section aria-labelledby="published-exams-heading" className="portal-panel min-w-0 overflow-hidden">
              <div className="border-b border-border px-5 py-5 sm:px-6"><p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">Student access</p><h2 id="published-exams-heading" className="mt-1 text-xl font-semibold tracking-tight">Available now</h2></div>
              {snapshot.current.length === 0 ? (
                <div className="px-5 py-8 sm:px-6"><p className="text-sm leading-6 text-muted-foreground">No examinations are published yet. Open a draft to finish and publish it.</p><Link to="/admin/exams" className="mt-4 inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-primary underline-offset-4 hover:underline">Open drafts <ArrowRight className="size-4" aria-hidden="true" /></Link></div>
              ) : (
                <ul className="divide-y divide-border">{snapshot.current.map((exam) => (
                  <li key={exam.id} className="portal-list-row px-5 py-4 sm:px-6"><Link to={`/admin/exams/${exam.id}`} className="inline-flex min-h-11 items-center break-words text-base font-semibold text-foreground underline-offset-4 hover:text-primary hover:underline">{exam.title}</Link><p className="mt-1 text-xs text-muted-foreground">{exam.question_count} questions · {exam.duration_minutes} minutes</p></li>
                ))}</ul>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
