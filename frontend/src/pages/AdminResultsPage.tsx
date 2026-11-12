import { ArrowRight, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyStatePanel, ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { getAdminExamResults, listAdminExams } from "@/features/admin/adminApi";
import { extractAdminApiError, formatDecimal } from "@/features/admin/adminUtils";
import { ExamStatusBadge } from "@/features/admin/components/ExamStatusBadge";
import type { ExamAdminOut, ExamAdminResultsResponse } from "@/types/adminExam";

export function AdminResultsPage() {
  const [exams, setExams] = useState<ExamAdminOut[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [results, setResults] = useState<ExamAdminResultsResponse | null>(null);
  const [query, setQuery] = useState("");
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [examError, setExamError] = useState<string | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoadingExams(true);
    setExamError(null);
    listAdminExams(undefined, { signal: controller.signal })
      .then((items) => {
        if (!controller.signal.aborted) setExams(items);
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setExamError(extractAdminApiError(error, "Examinations could not be loaded.").message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingExams(false);
      });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setLoadingResults(true);
    setResults(null);
    setResultsError(null);
    getAdminExamResults(selectedId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setResults(data);
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setResultsError(extractAdminApiError(error, "Results could not be loaded.").message);
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoadingResults(false);
      });
    return () => controller.abort();
  }, [selectedId, reload]);

  const visibleExams = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return exams.filter((exam) => exam.title.toLocaleLowerCase().includes(term));
  }, [exams, query]);
  const selectedExam = exams.find((exam) => exam.id === selectedId);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Administration"
        title="Results"
        description="Choose an examination to review submissions and outcomes."
      />

      {loadingExams ? (
        <LoadingStatePanel label="Loading examinations..." cards={3} />
      ) : examError ? (
        <ErrorStatePanel title="Could not load examinations" message={examError} onRetry={() => setReload((value) => value + 1)} />
      ) : exams.length === 0 ? (
        <EmptyStatePanel title="No examinations yet" description="Create an examination to start collecting results." action={<Button asChild><Link to="/admin/exams/new">Create examination</Link></Button>} />
      ) : (
        <div className="grid gap-6 lg:grid-cols-[minmax(250px,0.85fr)_minmax(0,1.5fr)]">
          <section aria-labelledby="results-exams-heading" className="min-w-0 space-y-3">
            <h2 id="results-exams-heading" className="text-lg font-semibold">Examinations</h2>
            <div className="relative">
              <Label htmlFor="results-exam-search" className="sr-only">Search examinations</Label>
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
              <Input id="results-exam-search" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search examinations" className="pl-9" />
            </div>
            {visibleExams.length === 0 ? <p className="py-6 text-sm text-muted-foreground">No examinations match your search.</p> : (
              <div className="space-y-2">
                {visibleExams.map((exam) => (
                  <button
                    key={exam.id}
                    type="button"
                    aria-pressed={selectedId === exam.id}
                    onClick={() => setSelectedId(exam.id)}
                    className={`flex min-h-16 w-full items-center justify-between gap-3 rounded-lg border px-4 py-3 text-left transition-colors hover:bg-muted/60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring ${selectedId === exam.id ? "border-primary bg-primary/5" : "border-border"}`}
                  >
                    <span className="min-w-0">
                      <span className="block truncate font-medium">{exam.title}</span>
                      <span className="mt-1 block text-xs text-muted-foreground">{exam.question_count} questions</span>
                    </span>
                    <ExamStatusBadge status={exam.status} />
                  </button>
                ))}
              </div>
            )}
          </section>

          <section aria-labelledby="results-detail-heading" className="min-w-0 lg:border-l lg:pl-6">
            <h2 id="results-detail-heading" className="text-lg font-semibold">{selectedExam?.title ?? "Examination results"}</h2>
            {!selectedId ? (
              <p className="mt-3 text-sm text-muted-foreground">Select an examination to see its results.</p>
            ) : loadingResults ? (
              <div className="mt-4"><LoadingStatePanel label="Loading results..." cards={2} /></div>
            ) : resultsError ? (
              <div className="mt-4"><ErrorStatePanel title="Could not load results" message={resultsError} onRetry={() => setReload((value) => value + 1)} /></div>
            ) : results ? (
              <div className="mt-4 space-y-6">
                <div className="grid grid-cols-2 gap-x-5 gap-y-4 border-y py-5 sm:grid-cols-4">
                  <div><p className="text-xs text-muted-foreground">Attempts</p><p className="text-xl font-semibold tabular-nums">{results.total_attempts}</p></div>
                  <div><p className="text-xs text-muted-foreground">Completed</p><p className="text-xl font-semibold tabular-nums">{results.summary.completed_attempts}</p></div>
                  <div><p className="text-xs text-muted-foreground">Average score</p><p className="text-xl font-semibold tabular-nums">{formatDecimal(results.summary.average_percentage, "%")}</p></div>
                  <div><p className="text-xs text-muted-foreground">Pass rate</p><p className="text-xl font-semibold tabular-nums">{formatDecimal(results.summary.pass_rate, "%")}</p></div>
                </div>
                {results.total_attempts === 0 ? (
                  <p className="text-sm text-muted-foreground">No candidates have started this examination yet.</p>
                ) : (
                  <p className="text-sm text-muted-foreground">Review candidate scores, submission times, and individual attempts in the examination report.</p>
                )}
                <Button asChild>
                  <Link to={`/admin/exams/${selectedId}/results`}>Open examination report <ArrowRight className="size-4" aria-hidden="true" /></Link>
                </Button>
              </div>
            ) : null}
          </section>
        </div>
      )}
    </div>
  );
}
