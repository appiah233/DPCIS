import {
  BarChart3,
  BookOpenCheck,
  FileText,
  Lock,
  Pencil,
  Plus,
  RefreshCw,
  Search,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/dialog";
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
import { deleteAdminExam, listAdminExams } from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  formatDateTime,
  formatDecimal,
} from "@/features/admin/adminUtils";
import { ExamStatusBadge } from "@/features/admin/components/ExamStatusBadge";
import type { ExamAdminOut, ExamStatus } from "@/types/adminExam";

type StatusFilter = "ALL" | ExamStatus;

const FILTER_OPTIONS: readonly { value: StatusFilter; label: string }[] = [
  { value: "ALL", label: "All" },
  { value: "DRAFT", label: "Draft" },
  { value: "PUBLISHED", label: "Published" },
  { value: "CLOSED", label: "Closed" },
];

export function AdminDashboardPage() {
  const [exams, setExams] = useState<ExamAdminOut[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const [examToDelete, setExamToDelete] = useState<ExamAdminOut | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);

  const triggerReload = useCallback(() => {
    setReloadToken((n) => n + 1);
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setErrorMessage(null);

    listAdminExams(undefined, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setExams(data);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setErrorMessage(
            extractAdminApiError(error, "Unable to load examinations.").message,
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
  }, [reloadToken]);

  const counts = useMemo(() => {
    let draft = 0;
    let published = 0;
    let closed = 0;
    for (const exam of exams) {
      if (exam.status === "DRAFT") draft += 1;
      else if (exam.status === "PUBLISHED") published += 1;
      else if (exam.status === "CLOSED") closed += 1;
    }
    return {
      all: exams.length,
      draft,
      published,
      closed,
    };
  }, [exams]);

  const filteredExams = useMemo(() => {
    const query = searchQuery.trim().toLocaleLowerCase();
    return exams.filter((exam) => {
      if (statusFilter !== "ALL" && exam.status !== statusFilter) {
        return false;
      }
      if (!query) {
        return true;
      }
      return (
        exam.title.toLocaleLowerCase().includes(query) ||
        (exam.description?.toLocaleLowerCase().includes(query) ?? false)
      );
    });
  }, [exams, statusFilter, searchQuery]);

  const handleConfirmDelete = async () => {
    if (!examToDelete || isDeleting) {
      return;
    }
    setIsDeleting(true);
    setActionError(null);
    setActionNotice(null);

    try {
      await deleteAdminExam(examToDelete.id);
      const deletedTitle = examToDelete.title;
      setExams((prev) => prev.filter((item) => item.id !== examToDelete.id));
      setExamToDelete(null);
      setActionNotice(`Deleted draft examination "${deletedTitle}".`);
    } catch (error) {
      setActionError(
        extractAdminApiError(error, "Unable to delete draft examination.").message,
      );
      setExamToDelete(null);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Admin Dashboard"
        title="Examinations"
        description="Create examinations, add multiple-choice questions, manage Draft, Published, and Closed exams, and review student attempts and results."
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
            <Button asChild>
              <Link to="/admin/exams/new">
                <Plus className="size-4" aria-hidden="true" />
                <span>Create Examination</span>
              </Link>
            </Button>
          </>
        }
      />

      {actionError ? (
        <Alert variant="destructive" role="alert">
          <AlertTitle>Action could not be completed</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      ) : null}

      {actionNotice ? (
        <Alert variant="success" role="status">
          <AlertTitle>Examination updated</AlertTitle>
          <AlertDescription>{actionNotice}</AlertDescription>
        </Alert>
      ) : null}

      {isLoading ? (
        <LoadingStatePanel label="Loading examinations..." cards={4} />
      ) : errorMessage ? (
        <ErrorStatePanel
          title="Unable to load examinations"
          message={errorMessage}
          onRetry={triggerReload}
        />
      ) : (
        <>
          <section aria-label="Examination counts" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardHeader className="flex-row items-center justify-between gap-2 pb-2">
                <CardTitle as="h2" className="text-sm font-medium text-muted-foreground">
                  Total Examinations
                </CardTitle>
                <FileText className="size-4 text-muted-foreground" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold tabular-nums text-foreground">{counts.all}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-center justify-between gap-2 pb-2">
                <CardTitle as="h2" className="text-sm font-medium text-muted-foreground">
                  Draft
                </CardTitle>
                <Pencil className="size-4 text-warning" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold tabular-nums text-foreground">{counts.draft}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-center justify-between gap-2 pb-2">
                <CardTitle as="h2" className="text-sm font-medium text-muted-foreground">
                  Published
                </CardTitle>
                <BookOpenCheck className="size-4 text-success" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold tabular-nums text-foreground">{counts.published}</p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex-row items-center justify-between gap-2 pb-2">
                <CardTitle as="h2" className="text-sm font-medium text-muted-foreground">
                  Closed
                </CardTitle>
                <Lock className="size-4 text-muted-foreground" aria-hidden="true" />
              </CardHeader>
              <CardContent>
                <p className="text-2xl font-bold tabular-nums text-foreground">{counts.closed}</p>
              </CardContent>
            </Card>
          </section>

          {exams.length === 0 ? (
            <EmptyStatePanel
              title="No examinations created yet"
              description="Start by creating a draft examination, setting timing and pass mark rules, and adding questions."
              action={
                <Button asChild>
                  <Link to="/admin/exams/new">
                    <Plus className="size-4" aria-hidden="true" />
                    <span>Create Examination</span>
                  </Link>
                </Button>
              }
            />
          ) : (
            <section aria-labelledby="exam-directory-heading" className="space-y-4">
              <h2 id="exam-directory-heading" className="visually-hidden">
                Examinations Directory
              </h2>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex flex-wrap gap-2" role="group" aria-label="Filter by status">
                  {FILTER_OPTIONS.map((option) => {
                    const count =
                      option.value === "ALL"
                        ? counts.all
                        : option.value === "DRAFT"
                          ? counts.draft
                          : option.value === "PUBLISHED"
                            ? counts.published
                            : counts.closed;
                    const isSelected = statusFilter === option.value;
                    return (
                      <Button
                        key={option.value}
                        type="button"
                        variant={isSelected ? "default" : "outline"}
                        size="sm"
                        aria-pressed={isSelected}
                        onClick={() => setStatusFilter(option.value)}
                      >
                        <span>
                          {option.label} ({count})
                        </span>
                      </Button>
                    );
                  })}
                </div>

                <div className="relative w-full sm:w-72">
                  <Label htmlFor="admin-exam-search" className="visually-hidden">
                    Search examinations by title
                  </Label>
                  <Search
                    className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <Input
                    id="admin-exam-search"
                    type="search"
                    value={searchQuery}
                    placeholder="Search examinations..."
                    className="pl-9"
                    onChange={(event) => setSearchQuery(event.target.value)}
                  />
                </div>
              </div>

              {filteredExams.length === 0 ? (
                <EmptyStatePanel
                  title="No examinations match your filters"
                  description="Clear the search box or switch the status filter to view other examinations."
                  action={
                    <Button
                      type="button"
                      variant="outline"
                      onClick={() => {
                        setStatusFilter("ALL");
                        setSearchQuery("");
                      }}
                    >
                      Reset filters
                    </Button>
                  }
                />
              ) : (
                <ResponsiveTable caption="Examinations directory" hideCaption>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Examination</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Questions</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Pass Mark</TableHead>
                      <TableHead>Max Attempts</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead>Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filteredExams.map((exam) => (
                      <TableRow key={exam.id}>
                        <TableRowHead>
                          <div className="min-w-0 space-y-1">
                            <Link
                              to={`/admin/exams/${exam.id}`}
                              className="inline-flex min-h-11 items-center py-1 break-words font-semibold text-foreground underline-offset-4 hover:text-primary hover:underline"
                            >
                              {exam.title}
                            </Link>
                            {exam.description ? (
                              <p className="line-clamp-2 text-xs font-normal text-muted-foreground">
                                {exam.description}
                              </p>
                            ) : null}
                          </div>
                        </TableRowHead>

                        <TableCell label="Status">
                          <ExamStatusBadge status={exam.status} />
                        </TableCell>

                        <TableCell label="Questions" className="tabular-nums">
                          <span>{exam.question_count}</span>
                          {exam.question_limit !== null ? (
                            <span className="ml-1 text-xs text-muted-foreground">
                              (limit {exam.question_limit})
                            </span>
                          ) : null}
                        </TableCell>

                        <TableCell label="Duration" className="tabular-nums">
                          {exam.duration_minutes} min
                        </TableCell>

                        <TableCell label="Pass Mark" className="tabular-nums">
                          {formatDecimal(exam.pass_mark, "%")}
                        </TableCell>

                        <TableCell label="Max Attempts" className="tabular-nums">
                          {exam.max_attempts}
                        </TableCell>

                        <TableCell label="Updated" className="text-xs text-muted-foreground">
                          {formatDateTime(exam.updated_at)}
                        </TableCell>

                        <TableCell label="Actions" stackOnMobile>
                          <div className="flex flex-wrap gap-2">
                            <Button asChild variant="outline" size="sm">
                              <Link to={`/admin/exams/${exam.id}`}>
                                {exam.status === "DRAFT" ? "Edit Draft" : "View Exam"}
                              </Link>
                            </Button>

                            <Button asChild variant="outline" size="sm">
                              <Link to={`/admin/exams/${exam.id}/results`}>
                                <BarChart3 className="size-4" aria-hidden="true" />
                                <span>Student Results</span>
                              </Link>
                            </Button>

                            {exam.status === "DRAFT" ? (
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="text-destructive hover:bg-destructive-subtle hover:text-destructive"
                                onClick={() => setExamToDelete(exam)}
                              >
                                <Trash2 className="size-4" aria-hidden="true" />
                                <span>Delete</span>
                              </Button>
                            ) : null}
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </ResponsiveTable>
              )}
            </section>
          )}
        </>
      )}

      <ConfirmDialog
        open={examToDelete !== null}
        onOpenChange={(open) => {
          if (!open && !isDeleting) {
            setExamToDelete(null);
          }
        }}
        title="Delete draft examination?"
        description={
          examToDelete
            ? `Permanently delete "${examToDelete.title}" and all of its draft questions? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete draft"
        confirmVariant="destructive"
        isPending={isDeleting}
        onConfirm={() => void handleConfirmDelete()}
      />
    </div>
  );
}
