import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { getAdminExamResults, listAdminExams } from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  formatDateTime,
  formatDecimal,
} from "@/features/admin/adminUtils";
import { ExamStatusBadge } from "@/features/admin/components/ExamStatusBadge";
import { useOptionalAuth } from "@/features/auth/useAuth";
import type { ExamAdminOut, ExamResultsSummary } from "@/types/adminExam";

export function AdminOverviewPage() {
  const auth = useOptionalAuth();
  const [exams, setExams] = useState<ExamAdminOut[]>([]);
  const [spotlightSummary, setSpotlightSummary] =
    useState<ExamResultsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const retry = useCallback(() => setReload((value) => value + 1), []);

  const firstName = useMemo(() => {
    const raw = auth?.identity?.display_name?.trim();
    if (!raw) {
      return "Dexta";
    }
    const tokens = raw
      .split(/\s+/)
      .filter((part) => !/^(dr|mr|mrs|ms|prof)\.?$/i.test(part));
    return tokens[0] || raw.split(/\s+/)[0] || "Dexta";
  }, [auth?.identity?.display_name]);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    listAdminExams(undefined, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setExams(data);
        }
      })
      .catch((cause) => {
        if (!controller.signal.aborted) {
          setError(
            extractAdminApiError(cause, "Unable to load your examinations.").message,
          );
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [reload]);

  const snapshot = useMemo(() => {
    const recent = [...exams]
      .sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))
      .slice(0, 5);
    const current = exams
      .filter((exam) => exam.status === "PUBLISHED")
      .sort(
        (a, b) =>
          Date.parse(b.published_at ?? b.updated_at) -
          Date.parse(a.published_at ?? a.updated_at),
      );
    const featured = current[0] ?? recent[0] ?? null;

    return {
      total: exams.length,
      draft: exams.filter((exam) => exam.status === "DRAFT").length,
      published: current.length,
      closed: exams.filter((exam) => exam.status === "CLOSED").length,
      recent,
      featured,
    };
  }, [exams]);

  useEffect(() => {
    const featuredId = snapshot.featured?.id;
    if (!featuredId) {
      setSpotlightSummary(null);
      return;
    }
    const controller = new AbortController();
    getAdminExamResults(featuredId, { signal: controller.signal })
      .then((response) => {
        if (!controller.signal.aborted) {
          setSpotlightSummary(response.summary);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setSpotlightSummary(null);
        }
      });
    return () => controller.abort();
  }, [snapshot.featured?.id]);

  const donutBackground = useMemo(() => {
    if (snapshot.total <= 0) {
      return "var(--subtle)";
    }
    const pubPct = (snapshot.published / snapshot.total) * 100;
    const draftEndPct =
      ((snapshot.published + snapshot.draft) / snapshot.total) * 100;
    return `conic-gradient(var(--ok) 0 ${pubPct.toFixed(1)}%, var(--warn-donut) ${pubPct.toFixed(1)}% ${draftEndPct.toFixed(1)}%, var(--line-strong) ${draftEndPct.toFixed(1)}% 100%)`;
  }, [snapshot.draft, snapshot.published, snapshot.total]);

  const submittedCount = spotlightSummary?.completed_attempts ?? 0;
  const averageScoreLabel =
    spotlightSummary?.average_percentage !== null &&
    spotlightSummary?.average_percentage !== undefined
      ? formatDecimal(spotlightSummary.average_percentage, "%")
      : "0%";
  const passRateLabel =
    spotlightSummary?.pass_rate !== null &&
    spotlightSummary?.pass_rate !== undefined
      ? formatDecimal(spotlightSummary.pass_rate, "%")
      : "0%";

  return (
    <section id="overview">
      <PageHeader
        eyebrow="Overview"
        title={`Good afternoon, ${firstName}`}
        description="Here’s where your examinations stand today."
        action={
          <Link className="admin-btn p" to="/admin/exams/new">
            <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 5v14M5 12h14" />
            </svg>
            Create examination
          </Link>
        }
      />

      {loading ? (
        <LoadingStatePanel label="Loading examination overview..." cards={3} />
      ) : error ? (
        <ErrorStatePanel
          title="Could not load overview"
          message={error}
          onRetry={retry}
        />
      ) : exams.length === 0 ? (
        <div className="admin-card">
          <div className="admin-empty">
            <div className="admin-ic">
              <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M2 4h7a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H2zM22 4h-7a3 3 0 0 0-3 3v14a2 2 0 0 1 2-2h8z" />
              </svg>
            </div>
            <b>Your first examination starts here</b>
            Create a draft, add questions, then publish when it is ready for students.
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
        <>
          {snapshot.featured ? (
            <div className="admin-spot">
              <div>
                <span className="admin-live">
                  <i className="admin-dot" aria-hidden="true" />
                  {snapshot.featured.status === "PUBLISHED"
                    ? "Live for students"
                    : snapshot.featured.status === "CLOSED"
                      ? "Closed examination"
                      : "Draft in preparation"}
                </span>
                <h2>{snapshot.featured.title}</h2>
                <p>
                  {snapshot.featured.question_count}{" "}
                  {snapshot.featured.question_count === 1 ? "question" : "questions"},{" "}
                  {snapshot.featured.duration_minutes} minutes, pass mark{" "}
                  {formatDecimal(snapshot.featured.pass_mark, "%")}
                </p>
                <div className="admin-acts">
                  <Link
                    className="admin-btn w"
                    to={`/admin/exams/${snapshot.featured.id}/results`}
                  >
                    View results
                  </Link>
                  <Link
                    className="admin-btn gl"
                    to={`/admin/exams/${snapshot.featured.id}`}
                  >
                    Manage examination
                  </Link>
                </div>
              </div>

              <div className="admin-sst">
                <div>
                  <b>{submittedCount}</b>
                  <span>
                    {submittedCount === 1
                      ? "Attempt submitted"
                      : "Attempts submitted"}
                  </span>
                </div>
                <div>
                  <b>{averageScoreLabel}</b>
                  <span>Average score</span>
                </div>
                <div>
                  <b>{passRateLabel}</b>
                  <span>Pass rate</span>
                </div>
              </div>
            </div>
          ) : null}

          <div className="admin-kpis">
            <div className="admin-card admin-kpi">
              <div className="admin-chip c1" aria-hidden="true">
                <svg className="admin-icon" viewBox="0 0 24 24">
                  <path d="M2 4h7a3 3 0 0 1 3 3v14a2 2 0 0 0-2-2H2zM22 4h-7a3 3 0 0 0-3 3v14a2 2 0 0 1 2-2h8z" />
                </svg>
              </div>
              <div>
                <small>Total examinations</small>
                <b>{snapshot.total}</b>
                <em>Across your library</em>
              </div>
            </div>

            <div className="admin-card admin-kpi">
              <div className="admin-chip c4" aria-hidden="true">
                <svg className="admin-icon" viewBox="0 0 24 24">
                  <path d="M6 3h8l4 4v14H6zM14 3v4h4" />
                </svg>
              </div>
              <div>
                <small>Drafts in progress</small>
                <b>{snapshot.draft}</b>
                <em>Not visible to students</em>
              </div>
            </div>

            <div className="admin-card admin-kpi">
              <div className="admin-chip c2" aria-hidden="true">
                <svg className="admin-icon" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="2" />
                  <path d="M7 7a7 7 0 0 0 0 10M17 7a7 7 0 0 1 0 10" />
                </svg>
              </div>
              <div>
                <small>Published</small>
                <b>{snapshot.published}</b>
                <em>Open to students now</em>
              </div>
            </div>

            <div className="admin-card admin-kpi">
              <div className="admin-chip c3" aria-hidden="true">
                <svg className="admin-icon" viewBox="0 0 24 24">
                  <circle cx="12" cy="12" r="9" />
                  <path d="M12 7v5l3 2" />
                </svg>
              </div>
              <div>
                <small>Closed</small>
                <b>{snapshot.closed}</b>
                <em>
                  {snapshot.closed === 0 ? "No archived exams" : "Archived sittings"}
                </em>
              </div>
            </div>
          </div>

          <div className="admin-g2">
            <div className="admin-card">
              <div className="admin-ch">
                <h2>Recently updated</h2>
                <Link to="/admin/exams">View all</Link>
              </div>
              {snapshot.recent.map((exam) => (
                <Link
                  key={exam.id}
                  to={`/admin/exams/${exam.id}`}
                  className="admin-row"
                >
                  <div className="admin-ic" aria-hidden="true">
                    {exam.status === "PUBLISHED" ? (
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="2" />
                        <path d="M7 7a7 7 0 0 0 0 10M17 7a7 7 0 0 1 0 10" />
                      </svg>
                    ) : exam.status === "CLOSED" ? (
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <circle cx="12" cy="12" r="9" />
                        <path d="M12 7v5l3 2" />
                      </svg>
                    ) : (
                      <svg className="admin-icon" viewBox="0 0 24 24">
                        <path d="M4 20h4L19 9l-4-4L4 16z" />
                      </svg>
                    )}
                  </div>
                  <div className="admin-t">
                    <b>{exam.title}</b>
                    <span>Updated {formatDateTime(exam.updated_at)}</span>
                  </div>
                  <ExamStatusBadge status={exam.status} />
                </Link>
              ))}
            </div>

            <div className="admin-stack">
              <div className="admin-card">
                <div className="admin-ch">
                  <h2>Library status</h2>
                </div>
                <div className="admin-sp">
                  <div
                    className="admin-donut"
                    data-n={snapshot.total}
                    style={{ background: donutBackground }}
                    role="img"
                    aria-label={`${snapshot.published} published, ${snapshot.draft} drafts, ${snapshot.closed} closed`}
                  />
                  <div className="admin-lg">
                    <span>
                      <i style={{ background: "var(--ok)" }} />
                      Published {snapshot.published}
                    </span>
                    <span>
                      <i style={{ background: "var(--warn-donut)" }} />
                      Draft {snapshot.draft}
                    </span>
                    <span>
                      <i style={{ background: "var(--line-strong)" }} />
                      Closed {snapshot.closed}
                    </span>
                  </div>
                </div>
              </div>

              <div className="admin-card admin-qa">
                <div className="admin-ch">
                  <h2>Quick actions</h2>
                </div>
                <Link to="/admin/exams/new">
                  <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M12 5v14M5 12h14" />
                  </svg>
                  Create examination
                  <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m9 6 6 6-6 6" />
                  </svg>
                </Link>
                <Link to="/admin/exams">
                  <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M6 3h8l4 4v14H6zM14 3v4h4" />
                  </svg>
                  Import questions from PDF
                  <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m9 6 6 6-6 6" />
                  </svg>
                </Link>
                <Link to="/admin/results">
                  <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
                  </svg>
                  Review student results
                  <svg className="admin-icon" viewBox="0 0 24 24" aria-hidden="true">
                    <path d="m9 6 6 6-6 6" />
                  </svg>
                </Link>
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
