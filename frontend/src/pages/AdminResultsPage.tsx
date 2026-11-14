import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import {
  ErrorStatePanel,
  LoadingStatePanel,
} from "@/components/ui/state-panel";
import { getAdminExamResults, listAdminExams } from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  formatDateTime,
  formatDecimal,
} from "@/features/admin/adminUtils";
import { AttemptDetailDialog } from "@/features/admin/components/AttemptDetailDialog";
import { ExamStatusBadge } from "@/features/admin/components/ExamStatusBadge";
import type {
  ExamAdminOut,
  ExamAdminResultsResponse,
} from "@/types/adminExam";

type OutcomeFilter = "ALL" | "PASSED" | "FAILED";

function getInitials(label: string | null | undefined): string {
  const cleaned = (label ?? "").trim();
  if (!cleaned) {
    return "ST";
  }
  const parts = cleaned.split(/[\s._-]+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[1][0]}`.toUpperCase();
  }
  return cleaned.slice(0, 2).toUpperCase();
}

function getSubmissionSubtitle(reason: string | null | undefined): string {
  if (reason === "STUDENT_SUBMITTED") {
    return "Submitted by student";
  }
  if (reason === "TIMER_EXPIRED") {
    return "Timer expired";
  }
  return "In progress";
}

export function AdminResultsPage() {
  const [exams, setExams] = useState<ExamAdminOut[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [resultsMap, setResultsMap] = useState<
    Record<string, ExamAdminResultsResponse>
  >({});
  const [query, setQuery] = useState("");
  const [outcomeFilter, setOutcomeFilter] = useState<OutcomeFilter>("ALL");
  const [loadingExams, setLoadingExams] = useState(true);
  const [loadingResults, setLoadingResults] = useState(false);
  const [examError, setExamError] = useState<string | null>(null);
  const [resultsError, setResultsError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [inspectedAttemptId, setInspectedAttemptId] = useState<string | null>(
    null,
  );

  useEffect(() => {
    const controller = new AbortController();
    setLoadingExams(true);
    setExamError(null);
    listAdminExams(undefined, { signal: controller.signal })
      .then((items) => {
        if (controller.signal.aborted) {
          return;
        }
        setExams(items);
        if (items.length > 0) {
          const preferred =
            items.find((item) => item.status === "PUBLISHED") ?? items[0];
          setSelectedId((prev) =>
            prev && items.some((i) => i.id === prev) ? prev : preferred.id,
          );
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setExamError(
            extractAdminApiError(error, "Examinations could not be loaded.")
              .message,
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingExams(false);
        }
      });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (exams.length === 0) {
      setResultsMap({});
      return;
    }
    const controller = new AbortController();
    void Promise.all(
      exams.map(async (exam) => {
        try {
          const data = await getAdminExamResults(exam.id, {
            signal: controller.signal,
          });
          return [exam.id, data] as const;
        } catch {
          return null;
        }
      }),
    ).then((entries) => {
      if (controller.signal.aborted) {
        return;
      }
      const next: Record<string, ExamAdminResultsResponse> = {};
      for (const entry of entries) {
        if (entry) {
          next[entry[0]] = entry[1];
        }
      }
      setResultsMap(next);
    });
    return () => controller.abort();
  }, [exams, reload]);

  useEffect(() => {
    if (!selectedId || resultsMap[selectedId]) {
      setResultsError(null);
      setLoadingResults(false);
      return;
    }
    const controller = new AbortController();
    setLoadingResults(true);
    setResultsError(null);
    getAdminExamResults(selectedId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setResultsMap((prev) => ({ ...prev, [selectedId]: data }));
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setResultsError(
            extractAdminApiError(error, "Results could not be loaded.").message,
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingResults(false);
        }
      });
    return () => controller.abort();
  }, [selectedId, resultsMap]);

  const visibleExams = useMemo(() => {
    const term = query.trim().toLocaleLowerCase();
    return exams.filter((exam) =>
      exam.title.toLocaleLowerCase().includes(term),
    );
  }, [exams, query]);

  const selectedExam = exams.find((exam) => exam.id === selectedId) ?? null;
  const results = selectedId ? (resultsMap[selectedId] ?? null) : null;

  const outcomeCounts = useMemo(() => {
    if (!results) {
      return { all: 0, passed: 0, failed: 0, inProgress: 0 };
    }
    let passed = 0;
    let failed = 0;
    let inProgress = 0;
    for (const attempt of results.attempts) {
      if (attempt.status === "GRADED") {
        if (attempt.passed) passed += 1;
        else failed += 1;
      } else {
        inProgress += 1;
      }
    }
    return {
      all: results.attempts.length,
      passed,
      failed,
      inProgress,
    };
  }, [results]);

  const histogramBuckets = useMemo(() => {
    const counts = [0, 0, 0, 0, 0];
    if (!results) {
      return { counts, max: 0 };
    }
    for (const attempt of results.attempts) {
      if (attempt.status !== "GRADED" || attempt.percentage === null) {
        continue;
      }
      const pct = Number.parseFloat(String(attempt.percentage));
      if (!Number.isFinite(pct)) {
        continue;
      }
      const idx = Math.min(4, Math.max(0, Math.floor(pct / 20)));
      counts[idx] += 1;
    }
    const max = Math.max(...counts, 0);
    return { counts, max };
  }, [results]);

  const filteredAttempts = useMemo(() => {
    if (!results) {
      return [];
    }
    return results.attempts.filter((attempt) => {
      if (outcomeFilter === "PASSED") {
        return attempt.status === "GRADED" && Boolean(attempt.passed);
      }
      if (outcomeFilter === "FAILED") {
        return attempt.status === "GRADED" && !attempt.passed;
      }
      return true;
    });
  }, [results, outcomeFilter]);

  const handleExportCsv = () => {
    if (!results) {
      return;
    }
    const header = [
      "Student",
      "Email",
      "Status",
      "Points Earned",
      "Points Available",
      "Percentage",
      "Outcome",
      "Submitted At",
    ];
    const rows = results.attempts.map((a) => [
      a.display_name ?? "Unnamed student",
      a.email ?? "",
      a.status,
      String(a.points_earned ?? ""),
      String(a.points_available ?? ""),
      String(a.percentage ?? ""),
      a.status === "GRADED" ? (a.passed ? "Passed" : "Did not pass") : "In progress",
      a.submitted_at ?? "",
    ]);
    const csv = [header, ...rows]
      .map((row) =>
        row.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(","),
      )
      .join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${results.exam_title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}-results.csv`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  const passMarkNum = results
    ? Math.min(
        100,
        Math.max(0, Number.parseFloat(String(results.pass_mark)) || 50),
      )
    : 50;

  return (
    <section id="results">
      <PageHeader
        eyebrow="Results"
        title="Student results"
        description="Pick an examination to review scores and submissions."
        action={
          <button
            className="admin-btn"
            type="button"
            disabled={!results || results.attempts.length === 0}
            onClick={handleExportCsv}
          >
            Export results
          </button>
        }
      />

      {loadingExams ? (
        <LoadingStatePanel label="Loading examinations..." cards={3} />
      ) : examError ? (
        <ErrorStatePanel
          title="Could not load examinations"
          message={examError}
          onRetry={() => setReload((value) => value + 1)}
        />
      ) : exams.length === 0 ? (
        <div className="admin-card">
          <div className="admin-empty">
            <div className="admin-ic">
              <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M6 3h8l4 4v14H6zM14 3v4h4" />
              </svg>
            </div>
            <b>No examinations yet</b>
            Create an examination to start collecting student results.
            <br />
            <Link className="admin-btn p" to="/admin/exams/new">
              <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 5v14M5 12h14" />
              </svg>
              Create examination
            </Link>
          </div>
        </div>
      ) : (
        <div className="admin-rg">
          <div className="admin-card">
            <div className="admin-ch">
              <h2>Examinations</h2>
            </div>
            <div className="admin-el">
              <label className="admin-sr" style={{ width: "100%" }}>
                <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="11" cy="11" r="7" />
                  <path d="m21 21-4.3-4.3" />
                </svg>
                <input
                  type="search"
                  style={{ width: "100%" }}
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search examinations"
                  aria-label="Search examinations"
                />
              </label>

              {visibleExams.map((exam) => {
                const examRes = resultsMap[exam.id];
                const attCount = examRes?.total_attempts ?? 0;
                const attemptText =
                  attCount === 0
                    ? "no attempts"
                    : `${attCount} ${attCount === 1 ? "attempt" : "attempts"}`;
                const isSelected = selectedId === exam.id;

                return (
                  <button
                    key={exam.id}
                    type="button"
                    className={`admin-ei${isSelected ? " on" : ""}`}
                    onClick={() => {
                      setSelectedId(exam.id);
                      setOutcomeFilter("ALL");
                    }}
                  >
                    <div className="admin-t">
                      <b>{exam.title}</b>
                      <span>
                        {exam.question_count}{" "}
                        {exam.question_count === 1 ? "question" : "questions"},{" "}
                        {attemptText}
                      </span>
                    </div>
                    <ExamStatusBadge status={exam.status} />
                  </button>
                );
              })}
            </div>
          </div>

          <div>
            {loadingResults && !results ? (
              <LoadingStatePanel label="Loading results..." cards={2} />
            ) : resultsError ? (
              <ErrorStatePanel
                title="Could not load results"
                message={resultsError}
                onRetry={() => setReload((value) => value + 1)}
              />
            ) : selectedExam &&
              selectedExam.status === "DRAFT" &&
              (!results || results.total_attempts === 0) ? (
              <div className="admin-card" id="p2">
                <div className="admin-empty">
                  <div className="admin-ic">
                    <svg
                      className="admin-icon"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path d="M6 3h8l4 4v14H6zM14 3v4h4" />
                    </svg>
                  </div>
                  <b>No attempts yet</b>
                  This examination is still a draft, so students can’t take it.
                  <br />
                  <Link
                    className="admin-btn p"
                    to={`/admin/exams/${selectedExam.id}`}
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
                </div>
              </div>
            ) : results ? (
              <div id="p1">
                <div className="admin-kpis k5">
                  <div className="admin-card admin-kpi v">
                    <div className="admin-chip c1" aria-hidden="true">
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <circle cx="9" cy="8" r="4" />
                        <path d="M2 21a7 7 0 0 1 14 0M17 4a4 4 0 0 1 0 8M22 21a6 6 0 0 0-4-5.6" />
                      </svg>
                    </div>
                    <div>
                      <small>Attempts</small>
                      <b>{results.total_attempts}</b>
                    </div>
                  </div>

                  <div className="admin-card admin-kpi v">
                    <div className="admin-chip c3" aria-hidden="true">
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
                      </svg>
                    </div>
                    <div>
                      <small>Average score</small>
                      <b>
                        {results.summary.completed_attempts > 0
                          ? formatDecimal(results.summary.average_percentage, "%")
                          : "0%"}
                      </b>
                    </div>
                  </div>

                  <div className="admin-card admin-kpi v">
                    <div className="admin-chip c2" aria-hidden="true">
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <path d="m5 12 5 5 9-10" />
                      </svg>
                    </div>
                    <div>
                      <small>Highest</small>
                      <b>
                        {results.summary.completed_attempts > 0
                          ? formatDecimal(results.summary.highest_percentage, "%")
                          : "0%"}
                      </b>
                    </div>
                  </div>

                  <div className="admin-card admin-kpi v">
                    <div className="admin-chip c4" aria-hidden="true">
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="9" />
                        <path d="M12 7v5l3 2" />
                      </svg>
                    </div>
                    <div>
                      <small>Lowest</small>
                      <b>
                        {results.summary.completed_attempts > 0
                          ? formatDecimal(results.summary.lowest_percentage, "%")
                          : "0%"}
                      </b>
                    </div>
                  </div>

                  <div className="admin-card admin-kpi v">
                    <div className="admin-chip c1" aria-hidden="true">
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="9" />
                        <circle cx="12" cy="12" r="4" />
                      </svg>
                    </div>
                    <div>
                      <small>Pass rate</small>
                      <b>
                        {results.summary.completed_attempts > 0
                          ? formatDecimal(results.summary.pass_rate, "%")
                          : "0%"}
                      </b>
                    </div>
                  </div>
                </div>

                <div className="admin-split">
                  <div className="admin-card">
                    <div className="admin-ch">
                      <h2>Score distribution</h2>
                      <span className="admin-pill nt">
                        Pass mark {formatDecimal(results.pass_mark, "%")}
                      </span>
                    </div>
                    <div
                      className="admin-chart"
                      role="img"
                      aria-label={`Score distribution across ${results.summary.completed_attempts} completed attempts`}
                    >
                      {histogramBuckets.counts.map((count, index) => {
                        const heightPct =
                          histogramBuckets.max > 0 && count > 0
                            ? Math.round((count / histogramBuckets.max) * 100)
                            : 0;
                        return (
                          <div
                            key={index}
                            className={`admin-bar${count > 0 ? " hi" : ""}`}
                            style={
                              count > 0
                                ? { height: `${Math.max(12, heightPct)}%` }
                                : undefined
                            }
                          />
                        );
                      })}
                      <div
                        className="admin-pm"
                        style={{ left: `${passMarkNum}%` }}
                      >
                        <span>Pass mark</span>
                      </div>
                    </div>
                    <div className="admin-xl">
                      <span>0–20%</span>
                      <span>21–40%</span>
                      <span>41–60%</span>
                      <span>61–80%</span>
                      <span>81–100%</span>
                    </div>
                  </div>

                  <div className="admin-card">
                    <div className="admin-ch">
                      <h2>Outcomes</h2>
                    </div>
                    <div
                      className="admin-stk"
                      role="img"
                      aria-label={`${outcomeCounts.failed} failed, ${outcomeCounts.passed} passed`}
                    >
                      {outcomeCounts.all > 0 ? (
                        <>
                          {outcomeCounts.passed > 0 ? (
                            <i
                              style={{
                                width: `${(outcomeCounts.passed / outcomeCounts.all) * 100}%`,
                                background: "var(--ok)",
                              }}
                            />
                          ) : null}
                          {outcomeCounts.failed > 0 ? (
                            <i
                              style={{
                                width: `${(outcomeCounts.failed / outcomeCounts.all) * 100}%`,
                                background: "var(--danger)",
                              }}
                            />
                          ) : null}
                          {outcomeCounts.inProgress > 0 ? (
                            <i
                              style={{
                                width: `${(outcomeCounts.inProgress / outcomeCounts.all) * 100}%`,
                                background: "var(--line-strong)",
                              }}
                            />
                          ) : null}
                        </>
                      ) : null}
                    </div>
                    <div
                      className="admin-lg"
                      style={{ padding: "0 20px 20px" }}
                    >
                      <span>
                        <i style={{ background: "var(--ok)" }} />
                        Passed {outcomeCounts.passed}
                      </span>
                      <span>
                        <i style={{ background: "var(--danger)" }} />
                        Did not pass {outcomeCounts.failed}
                      </span>
                      <span>
                        <i style={{ background: "var(--line-strong)" }} />
                        In progress {outcomeCounts.inProgress}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="admin-card">
                  <div className="admin-ch">
                    <h2>Submissions</h2>
                    <SegmentedControl ariaLabel="Filter outcome">
                      <SegmentedControlItem
                        active={outcomeFilter === "ALL"}
                        count={outcomeCounts.all}
                        onClick={() => setOutcomeFilter("ALL")}
                      >
                        All
                      </SegmentedControlItem>
                      <SegmentedControlItem
                        active={outcomeFilter === "PASSED"}
                        count={outcomeCounts.passed}
                        onClick={() => setOutcomeFilter("PASSED")}
                      >
                        Passed
                      </SegmentedControlItem>
                      <SegmentedControlItem
                        active={outcomeFilter === "FAILED"}
                        count={outcomeCounts.failed}
                        onClick={() => setOutcomeFilter("FAILED")}
                      >
                        Did not pass
                      </SegmentedControlItem>
                    </SegmentedControl>
                  </div>

                  {filteredAttempts.length === 0 ? (
                    <div className="admin-empty">
                      <div className="admin-ic">
                        <svg
                          className="admin-icon"
                          viewBox="0 0 24 24"
                          aria-hidden="true"
                        >
                          <circle cx="9" cy="8" r="4" />
                          <path d="M2 21a7 7 0 0 1 14 0M17 4a4 4 0 0 1 0 8M22 21a6 6 0 0 0-4-5.6" />
                        </svg>
                      </div>
                      <b>No submissions match</b>
                      Try switching the outcome filter above.
                    </div>
                  ) : (
                    <div className="admin-tw">
                      <table className="admin-table">
                        <thead>
                          <tr>
                            <th>Student</th>
                            <th className="n">Score</th>
                            <th>Outcome</th>
                            <th>Submitted</th>
                            <th aria-label="Actions" />
                          </tr>
                        </thead>
                        <tbody>
                          {filteredAttempts.map((row) => {
                            const isGraded = row.status === "GRADED";
                            const pctNum = isGraded
                              ? Math.min(
                                  100,
                                  Math.max(
                                    0,
                                    Number.parseFloat(String(row.percentage)) ||
                                      0,
                                  ),
                                )
                              : 0;
                            const studentName =
                              row.display_name ||
                              row.email ||
                              "Unnamed student";

                            return (
                              <tr key={row.attempt_id}>
                                <td>
                                  <div className="admin-mini">
                                    <div
                                      className="admin-av"
                                      style={{
                                        background: "var(--brand-50)",
                                        color: "var(--brand)",
                                      }}
                                      aria-hidden="true"
                                    >
                                      {getInitials(studentName)}
                                    </div>
                                    <div className="admin-tn">
                                      <b>{studentName}</b>
                                      <span>
                                        {getSubmissionSubtitle(
                                          row.submission_reason,
                                        )}
                                      </span>
                                    </div>
                                  </div>
                                </td>

                                <td className="n">
                                  {isGraded ? (
                                    <div className="admin-mini">
                                      <b>
                                        {formatDecimal(row.points_earned)} /{" "}
                                        {formatDecimal(row.points_available)}
                                      </b>
                                      <div
                                        className="admin-meter"
                                        aria-hidden="true"
                                      >
                                        <i
                                          style={{
                                            width: `${pctNum.toFixed(1)}%`,
                                            background: row.passed
                                              ? "var(--ok)"
                                              : "var(--danger)",
                                          }}
                                        />
                                      </div>
                                      <span>
                                        {formatDecimal(row.percentage, "%")}
                                      </span>
                                    </div>
                                  ) : (
                                    <span>Pending</span>
                                  )}
                                </td>

                                <td>
                                  {!isGraded ? (
                                    <span className="admin-pill nt">
                                      <svg
                                        className="admin-icon"
                                        viewBox="0 0 24 24"
                                        aria-hidden="true"
                                      >
                                        <circle cx="12" cy="12" r="9" />
                                        <path d="M12 7v5l3 2" />
                                      </svg>
                                      In progress
                                    </span>
                                  ) : row.passed ? (
                                    <span className="admin-pill ok">
                                      <svg
                                        className="admin-icon"
                                        viewBox="0 0 24 24"
                                        aria-hidden="true"
                                      >
                                        <path d="m5 12 5 5 9-10" />
                                      </svg>
                                      Passed
                                    </span>
                                  ) : (
                                    <span className="admin-pill dg">
                                      <svg
                                        className="admin-icon"
                                        viewBox="0 0 24 24"
                                        aria-hidden="true"
                                      >
                                        <path d="m6 6 12 12M18 6 6 18" />
                                      </svg>
                                      Did not pass
                                    </span>
                                  )}
                                </td>

                                <td>{formatDateTime(row.submitted_at)}</td>

                                <td>
                                  <div className="admin-act">
                                    <button
                                      className="admin-btn sm"
                                      type="button"
                                      onClick={() =>
                                        setInspectedAttemptId(row.attempt_id)
                                      }
                                    >
                                      View details
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              </div>
            ) : null}
          </div>
        </div>
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
    </section>
  );
}
