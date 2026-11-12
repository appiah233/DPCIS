import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Eye,
  RefreshCw,
  Search,
  Settings2,
  XCircle,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ResponsiveTable,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  TableRowHead,
} from "@/components/ui/responsive-table";
import {
  EmptyStatePanel,
  ErrorStatePanel,
  LoadingStatePanel,
} from "@/components/ui/state-panel";
import { getAdminExamResults } from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  formatDateTime,
  formatDecimal,
  formatSubmissionReason,
} from "@/features/admin/adminUtils";
import { AttemptDetailDialog } from "@/features/admin/components/AttemptDetailDialog";
import type { ExamAdminResultsResponse } from "@/types/adminExam";

type AttemptOutcomeFilter = "ALL" | "PASSED" | "FAILED" | "IN_PROGRESS";

const OUTCOME_FILTERS: readonly { value: AttemptOutcomeFilter; label: string }[] = [
  { value: "ALL", label: "All attempts" },
  { value: "PASSED", label: "Passed" },
  { value: "FAILED", label: "Failed" },
  { value: "IN_PROGRESS", label: "In progress" },
];

export function AdminExamResultsPage() {
  const { examId } = useParams<{ examId: string }>();

  const [results, setResults] = useState<ExamAdminResultsResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const [outcomeFilter, setOutcomeFilter] = useState<AttemptOutcomeFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [inspectedAttemptId, setInspectedAttemptId] = useState<string | null>(null);

  const triggerReload = useCallback(() => {
    setReloadToken((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!examId) {
      setIsLoading(false);
      setErrorMessage("No examination ID was provided.");
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage(null);

    getAdminExamResults(examId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setResults(data);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setErrorMessage(
            extractAdminApiError(error, "Unable to load examination results.").message,
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setIsLoading(false);
        }
      });

    return () => {
      controller.abort();
    };
  }, [examId, reloadToken]);

  const filteredAttempts = useMemo(() => {
    if (!results) {
      return [];
    }
    const query = searchQuery.trim().toLocaleLowerCase();
    return results.attempts.filter((attempt) => {
      if (outcomeFilter === "PASSED" && !(attempt.status === "GRADED" && attempt.passed)) {
        return false;
      }
      if (outcomeFilter === "FAILED" && !(attempt.status === "GRADED" && !attempt.passed)) {
        return false;
      }
      if (outcomeFilter === "IN_PROGRESS" && attempt.status === "GRADED") {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        (attempt.display_name?.toLocaleLowerCase().includes(query) ?? false) ||
        (attempt.email?.toLocaleLowerCase().includes(query) ?? false)
      );
    });
  }, [results, outcomeFilter, searchQuery]);

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Results Oversight"
          title="Loading Examination Results"
          description="Fetching server-computed aggregate metrics and student attempts..."
        />
        <LoadingStatePanel label="Loading examination results..." cards={4} />
      </div>
    );
  }

  if (errorMessage || !results) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Results Oversight"
          title="Results Unavailable"
          description="Could not retrieve results for this examination."
          action={
            <Button asChild variant="outline">
              <Link to="/admin">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Back to Dashboard</span>
              </Link>
            </Button>
          }
        />
        <ErrorStatePanel
          title="Could not load examination results"
          message={errorMessage ?? "Examination results not found."}
          onRetry={triggerReload}
        />
      </div>
    );
  }

  const { summary } = results;
  const hasCompleted = summary.completed_attempts > 0;

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Results Oversight"
        title={results.exam_title}
        description={`Pass mark: ${formatDecimal(results.pass_mark, "%")} · Total recorded attempts: ${results.total_attempts}`}
        action={
          <>
            <Button
              type="button"
              variant="outline"
              disabled={isLoading}
              onClick={triggerReload}
            >
              <RefreshCw className="size-4" aria-hidden="true" />
              <span>Refresh</span>
            </Button>
            {examId ? (
              <Button asChild variant="outline">
                <Link to={`/admin/exams/${examId}`}>
                  <Settings2 className="size-4" aria-hidden="true" />
                  <span>Manage Exam</span>
                </Link>
              </Button>
            ) : null}
            <Button asChild variant="outline">
              <Link to="/admin">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Dashboard</span>
              </Link>
            </Button>
          </>
        }
      />

      <section
        aria-label="Summary metrics"
        className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5"
      >
        <Card>
          <CardHeader className="pb-2">
            <CardTitle as="h2" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Completed Attempts
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold tabular-nums text-foreground">
              {summary.completed_attempts}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle as="h2" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Average Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold tabular-nums text-foreground">
              {hasCompleted ? formatDecimal(summary.average_percentage, "%") : "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle as="h2" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Highest Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold tabular-nums text-foreground">
              {hasCompleted ? formatDecimal(summary.highest_percentage, "%") : "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle as="h2" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Lowest Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold tabular-nums text-foreground">
              {hasCompleted ? formatDecimal(summary.lowest_percentage, "%") : "—"}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle as="h2" className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Pass Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-2xl font-bold tabular-nums text-foreground">
              {hasCompleted ? formatDecimal(summary.pass_rate, "%") : "—"}
            </p>
          </CardContent>
        </Card>
      </section>

      {results.attempts.length === 0 ? (
        <EmptyStatePanel
          title="No student attempts yet"
          description="Summary metrics and candidate attempt breakdowns will populate automatically once students begin this examination."
        />
      ) : (
        <section aria-labelledby="attempts-list-heading" className="space-y-4">
          <h2 id="attempts-list-heading" className="visually-hidden">
            Student Attempts
          </h2>
          {!hasCompleted ? (
            <Alert variant="default" role="status">
              <AlertTitle>No graded attempts completed yet</AlertTitle>
              <AlertDescription>
                {results.total_attempts} attempt{results.total_attempts === 1 ? " is" : "s are"}{" "}
                currently in progress. Aggregate percentages will appear once attempts are
                submitted or expire.
              </AlertDescription>
            </Alert>
          ) : null}

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-2" role="group" aria-label="Filter attempts">
              {OUTCOME_FILTERS.map((filter) => {
                const isSelected = outcomeFilter === filter.value;
                return (
                  <Button
                    key={filter.value}
                    type="button"
                    size="sm"
                    variant={isSelected ? "default" : "outline"}
                    aria-pressed={isSelected}
                    onClick={() => setOutcomeFilter(filter.value)}
                  >
                    {filter.label}
                  </Button>
                );
              })}
            </div>

            <div className="relative w-full sm:w-72">
              <Label htmlFor="admin-attempt-search" className="visually-hidden">
                Search students by name or email
              </Label>
              <Search
                className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                aria-hidden="true"
              />
              <Input
                id="admin-attempt-search"
                type="search"
                value={searchQuery}
                placeholder="Search student name or email..."
                className="pl-9"
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </div>
          </div>

          {filteredAttempts.length === 0 ? (
            <EmptyStatePanel
              title="No matching student attempts"
              description="Adjust your search query or outcome filter to view other recorded attempts."
              action={
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    setOutcomeFilter("ALL");
                    setSearchQuery("");
                  }}
                >
                  Reset filters
                </Button>
              }
            />
          ) : (
            <ResponsiveTable caption="Student examination attempts" hideCaption>
              <TableHeader>
                <TableRow>
                  <TableHead>Student</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Score</TableHead>
                  <TableHead>Percentage</TableHead>
                  <TableHead>Outcome</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Submitted</TableHead>
                  <TableHead>Reason</TableHead>
                  <TableHead>Details</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAttempts.map((row) => {
                  const isGraded = row.status === "GRADED";
                  return (
                    <TableRow key={row.attempt_id}>
                      <TableRowHead>
                        <div className="min-w-0">
                          <p className="break-words font-semibold text-foreground">
                            {row.display_name || "Unnamed student"}
                          </p>
                          <p className="break-all text-xs font-normal text-muted-foreground">
                            {row.email || "No email on record"}
                          </p>
                        </div>
                      </TableRowHead>

                      <TableCell label="Status">
                        <Badge variant={isGraded ? "default" : "secondary"}>
                          {row.status}
                        </Badge>
                      </TableCell>

                      <TableCell label="Score" className="tabular-nums">
                        {isGraded
                          ? `${formatDecimal(row.points_earned)} / ${formatDecimal(row.points_available)}`
                          : "Pending"}
                      </TableCell>

                      <TableCell label="Percentage" className="font-semibold tabular-nums">
                        {isGraded ? formatDecimal(row.percentage, "%") : "—"}
                      </TableCell>

                      <TableCell label="Outcome">
                        {!isGraded ? (
                          <Badge variant="warning">
                            <Clock className="size-3.5" aria-hidden="true" />
                            <span>In progress</span>
                          </Badge>
                        ) : row.passed ? (
                          <Badge variant="success">
                            <CheckCircle2 className="size-3.5" aria-hidden="true" />
                            <span>Passed</span>
                          </Badge>
                        ) : (
                          <Badge variant="destructive">
                            <XCircle className="size-3.5" aria-hidden="true" />
                            <span>Failed</span>
                          </Badge>
                        )}
                      </TableCell>

                      <TableCell label="Started" className="text-xs text-muted-foreground">
                        {formatDateTime(row.started_at)}
                      </TableCell>

                      <TableCell label="Submitted" className="text-xs text-muted-foreground">
                        {formatDateTime(row.submitted_at)}
                      </TableCell>

                      <TableCell label="Submission reason" className="text-xs">
                        {formatSubmissionReason(row.submission_reason)}
                      </TableCell>

                      <TableCell label="Details" stackOnMobile>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => setInspectedAttemptId(row.attempt_id)}
                        >
                          <Eye className="size-4" aria-hidden="true" />
                          <span>Inspect Attempt</span>
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </ResponsiveTable>
          )}
        </section>
      )}

      <AttemptDetailDialog
        attemptId={inspectedAttemptId}
        open={inspectedAttemptId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setInspectedAttemptId(null);
          }
        }}
      />
    </div>
  );
}
