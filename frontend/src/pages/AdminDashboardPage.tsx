import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ConfirmDialog } from "@/components/ui/dialog";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import {
  ErrorStatePanel,
  LoadingStatePanel,
} from "@/components/ui/state-panel";
import {
  closeAdminExam,
  createAdminExam,
  deleteAdminExam,
  getAdminExam,
  getAdminExamResults,
  listAdminExams,
  saveExamQuestions,
} from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  formatDateTime,
  formatDecimal,
  fromAdminQuestions,
  toQuestionCreates,
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
  const [attemptCounts, setAttemptCounts] = useState<Record<string, number>>({});
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionNotice, setActionNotice] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [searchQuery, setSearchQuery] = useState("");
  const [reloadToken, setReloadToken] = useState(0);

  const [examToDelete, setExamToDelete] = useState<ExamAdminOut | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [examToClose, setExamToClose] = useState<ExamAdminOut | null>(null);
  const [isClosing, setIsClosing] = useState(false);
  const [duplicatingId, setDuplicatingId] = useState<string | null>(null);

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

  useEffect(() => {
    if (exams.length === 0) {
      setAttemptCounts({});
      return;
    }
    const controller = new AbortController();
    void Promise.all(
      exams.map(async (exam) => {
        try {
          const res = await getAdminExamResults(exam.id, {
            signal: controller.signal,
          });
          return [exam.id, res.summary.completed_attempts] as const;
        } catch {
          return [exam.id, 0] as const;
        }
      }),
    ).then((pairs) => {
      if (!controller.signal.aborted) {
        setAttemptCounts(Object.fromEntries(pairs));
      }
    });
    return () => controller.abort();
  }, [exams]);

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

  const handleConfirmClose = async () => {
    if (!examToClose || isClosing) {
      return;
    }
    setIsClosing(true);
    setActionError(null);
    setActionNotice(null);

    try {
      const updated = await closeAdminExam(examToClose.id);
      setExams((prev) =>
        prev.map((item) => (item.id === updated.id ? updated : item)),
      );
      setExamToClose(null);
      setActionNotice(`Closed examination "${updated.title}".`);
    } catch (error) {
      setActionError(
        extractAdminApiError(error, "Unable to close examination.").message,
      );
      setExamToClose(null);
    } finally {
      setIsClosing(false);
    }
  };

  const handleDuplicateExam = async (exam: ExamAdminOut) => {
    if (duplicatingId) {
      return;
    }
    setDuplicatingId(exam.id);
    setActionError(null);
    setActionNotice(null);

    try {
      const fullExam = await getAdminExam(exam.id);
      const created = await createAdminExam({
        title: `${fullExam.title} (Copy)`,
        description: fullExam.description,
        instructions: fullExam.instructions,
        duration_minutes: fullExam.duration_minutes,
        pass_mark: fullExam.pass_mark,
        max_attempts: fullExam.max_attempts,
        question_limit: fullExam.question_limit,
        randomize_questions: fullExam.randomize_questions,
        randomize_options: fullExam.randomize_options,
        show_result: fullExam.show_result,
        show_correct_answers: fullExam.show_correct_answers,
      });
      if (fullExam.questions && fullExam.questions.length > 0) {
        const editable = fromAdminQuestions(fullExam.questions);
        await saveExamQuestions(created.id, toQuestionCreates(editable));
      }
      triggerReload();
      setActionNotice(`Duplicated "${exam.title}" as a new draft.`);
    } catch (error) {
      setActionError(
        extractAdminApiError(error, "Unable to duplicate examination.").message,
      );
    } finally {
      setDuplicatingId(null);
    }
  };

  return (
    <section id="examinations">
      <PageHeader
        eyebrow="Examinations"
        title="Manage examinations"
        description="Find, prepare and publish your examinations."
        action={
          <>
            <button
              className="admin-btn"
              type="button"
              disabled={isLoading}
              onClick={triggerReload}
            >
              <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M21 12a9 9 0 1 1-3-6.7L21 8M21 3v5h-5" />
              </svg>
              Refresh
            </button>
            <Link className="admin-btn p" to="/admin/exams/new">
              <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
              Create examination
            </Link>
          </>
        }
      />

      {actionError ? (
        <Alert variant="destructive" role="alert" className="mb-4">
          <AlertTitle>Action could not be completed</AlertTitle>
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      ) : null}

      {actionNotice ? (
        <Alert variant="success" role="status" className="mb-4">
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
        <div className="admin-card">
          <div className="admin-tb">
            <SegmentedControl ariaLabel="Filter by status">
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
                  <SegmentedControlItem
                    key={option.value}
                    active={isSelected}
                    count={count}
                    onClick={() => setStatusFilter(option.value)}
                  >
                    {option.label}
                  </SegmentedControlItem>
                );
              })}
            </SegmentedControl>

            <label className="admin-sr">
              <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="m21 21-4.3-4.3" />
              </svg>
              <input
                id="q"
                type="search"
                value={searchQuery}
                placeholder="Search examinations"
                aria-label="Search examinations"
                onChange={(event) => setSearchQuery(event.target.value)}
              />
            </label>
          </div>

          {filteredExams.length > 0 ? (
            <div className="admin-tw">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>Examination</th>
                    <th>Status</th>
                    <th className="n">Questions</th>
                    <th className="n">Duration</th>
                    <th className="n">Pass mark</th>
                    <th className="n">Attempts</th>
                    <th>Last updated</th>
                    <th aria-label="Actions" />
                  </tr>
                </thead>
                <tbody id="tb">
                  {filteredExams.map((exam) => {
                    const subLabel =
                      exam.status === "PUBLISHED"
                        ? "Opens to students now"
                        : exam.status === "CLOSED"
                          ? "Closed to new sittings"
                          : exam.question_count === 0
                            ? "No questions yet"
                            : `${exam.question_count} ${exam.question_count === 1 ? "question" : "questions"} ready`;
                    const attemptsCount = attemptCounts[exam.id] ?? 0;

                    return (
                      <tr key={exam.id} data-s={exam.status.toLowerCase()}>
                        <td className="admin-tn">
                          <Link
                            to={`/admin/exams/${exam.id}`}
                            className="no-underline hover:underline"
                          >
                            <b>{exam.title}</b>
                          </Link>
                          <span>{subLabel}</span>
                        </td>
                        <td>
                          <ExamStatusBadge status={exam.status} />
                        </td>
                        <td className="n">{exam.question_count}</td>
                        <td className="n">{exam.duration_minutes} min</td>
                        <td className="n">
                          {formatDecimal(exam.pass_mark, "%")}
                        </td>
                        <td className="n">{attemptsCount}</td>
                        <td>{formatDateTime(exam.updated_at)}</td>
                        <td>
                          <div className="admin-act">
                            {exam.status === "DRAFT" ? (
                              <Link
                                className="admin-btn sm p"
                                to={`/admin/exams/${exam.id}`}
                              >
                                <svg
                                  className="admin-icon"
                                  viewBox="0 0 24 24"
                                  aria-hidden="true"
                                >
                                  <path d="M4 20h4L19 9l-4-4L4 16z" />
                                </svg>
                                Edit draft
                              </Link>
                            ) : (
                              <>
                                <Link
                                  className="admin-btn sm"
                                  to={`/admin/exams/${exam.id}/results`}
                                >
                                  <svg
                                    className="admin-icon"
                                    viewBox="0 0 24 24"
                                    aria-hidden="true"
                                  >
                                    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
                                  </svg>
                                  Results
                                </Link>
                                <Link
                                  className="admin-btn sm p"
                                  to={`/admin/exams/${exam.id}`}
                                >
                                  View
                                </Link>
                              </>
                            )}

                            <details className="admin-dd">
                              <summary
                                className="admin-btn sm sq"
                                aria-label={`More actions for ${exam.title}`}
                              >
                                <svg
                                  className="admin-icon"
                                  viewBox="0 0 24 24"
                                  aria-hidden="true"
                                >
                                  <circle cx="5" cy="12" r="1.5" />
                                  <circle cx="12" cy="12" r="1.5" />
                                  <circle cx="19" cy="12" r="1.5" />
                                </svg>
                              </summary>
                              <div className="admin-dm">
                                <button
                                  type="button"
                                  disabled={duplicatingId === exam.id}
                                  onClick={(event) => {
                                    const details =
                                      event.currentTarget.closest("details");
                                    if (details) details.open = false;
                                    void handleDuplicateExam(exam);
                                  }}
                                >
                                  <svg
                                    className="admin-icon"
                                    viewBox="0 0 24 24"
                                    aria-hidden="true"
                                  >
                                    <rect
                                      x="9"
                                      y="9"
                                      width="12"
                                      height="12"
                                      rx="2"
                                    />
                                    <path d="M5 15V5a2 2 0 0 1 2-2h10" />
                                  </svg>
                                  Duplicate
                                </button>

                                {exam.status === "PUBLISHED" ? (
                                  <button
                                    type="button"
                                    onClick={(event) => {
                                      const details =
                                        event.currentTarget.closest("details");
                                      if (details) details.open = false;
                                      setExamToClose(exam);
                                    }}
                                  >
                                    <svg
                                      className="admin-icon"
                                      viewBox="0 0 24 24"
                                      aria-hidden="true"
                                    >
                                      <circle cx="12" cy="12" r="9" />
                                      <path d="M12 7v5l3 2" />
                                    </svg>
                                    Close examination
                                  </button>
                                ) : null}

                                {exam.status === "DRAFT" ? (
                                  <button
                                    type="button"
                                    className="d"
                                    onClick={(event) => {
                                      const details =
                                        event.currentTarget.closest("details");
                                      if (details) details.open = false;
                                      setExamToDelete(exam);
                                    }}
                                  >
                                    <svg
                                      className="admin-icon"
                                      viewBox="0 0 24 24"
                                      aria-hidden="true"
                                    >
                                      <path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3" />
                                    </svg>
                                    Delete draft
                                  </button>
                                ) : null}
                              </div>
                            </details>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="admin-empty" id="none">
              <div className="admin-ic">
                <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
              </div>
              <b>No examinations match</b>
              Try a different status or search term.
            </div>
          )}

          <div className="admin-tf" id="cnt">
            Showing {filteredExams.length} of {exams.length} examinations
          </div>
        </div>
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

      <ConfirmDialog
        open={examToClose !== null}
        onOpenChange={(open) => {
          if (!open && !isClosing) {
            setExamToClose(null);
          }
        }}
        title="Close examination?"
        description={
          examToClose
            ? `Close "${examToClose.title}" so students can no longer start new attempts? Submitted attempts will remain available in results.`
            : ""
        }
        confirmLabel="Close examination"
        confirmVariant="destructive"
        isPending={isClosing}
        onConfirm={() => void handleConfirmClose()}
      />
    </section>
  );
}
