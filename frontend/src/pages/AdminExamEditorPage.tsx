import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Lock,
  Send,
  Trash2,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { PageHeader } from "@/components/PageHeader";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import {
  closeAdminExam,
  deleteAdminExam,
  getAdminExam,
  publishAdminExam,
  saveExamQuestions,
  updateAdminExam,
} from "@/features/admin/adminApi";
import {
  computeQuestionsSignature,
  extractAdminApiError,
  formatDateTime,
  fromAdminQuestions,
  toQuestionCreates,
  type EditableQuestion,
} from "@/features/admin/adminUtils";
import { BulkParserPanel } from "@/features/admin/components/BulkParserPanel";
import { ExamSettingsForm } from "@/features/admin/components/ExamSettingsForm";
import { ExamStatusBadge } from "@/features/admin/components/ExamStatusBadge";
import { QuestionListEditor } from "@/features/admin/components/QuestionListEditor";
import type { ExamCreate, ExamWithQuestionsAdmin } from "@/types/adminExam";

export function AdminExamEditorPage() {
  const { examId } = useParams<{ examId: string }>();
  const navigate = useNavigate();

  const [exam, setExam] = useState<ExamWithQuestionsAdmin | null>(null);
  const [questions, setQuestions] = useState<EditableQuestion[]>([]);
  const [savedQuestionsSig, setSavedQuestionsSig] = useState<string>("[]");
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);
  const [activeSection, setActiveSection] = useState<"overview" | "questions" | "settings">("overview");

  const [settingsDirty, setSettingsDirty] = useState(false);
  const [isSavingSettings, setIsSavingSettings] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsSuccess, setSettingsSuccess] = useState<string | null>(null);

  const [isSavingQuestions, setIsSavingQuestions] = useState(false);
  const [questionsError, setQuestionsError] = useState<string | null>(null);
  const [questionsSuccess, setQuestionsSuccess] = useState<string | null>(null);

  const [lifecycleAction, setLifecycleAction] = useState<"publish" | "close" | "delete" | null>(
    null,
  );
  const [isLifecyclePending, setIsLifecyclePending] = useState(false);
  const [lifecycleError, setLifecycleError] = useState<{
    message: string;
    validationErrors: string[];
  } | null>(null);
  const [lifecycleSuccess, setLifecycleSuccess] = useState<string | null>(null);

  const triggerReload = useCallback(() => {
    setReloadToken((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!examId) {
      setIsLoading(false);
      setLoadError("No examination ID was provided.");
      return;
    }

    const controller = new AbortController();
    setIsLoading(true);
    setLoadError(null);

    getAdminExam(examId, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setExam(data);
          const mapped = fromAdminQuestions(data.questions);
          setQuestions(mapped);
          setSavedQuestionsSig(computeQuestionsSignature(mapped));
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setLoadError(
            extractAdminApiError(error, "Unable to load examination details.").message,
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

  const currentQuestionsSig = useMemo(
    () => computeQuestionsSignature(questions),
    [questions],
  );
  const questionsDirty = currentQuestionsSig !== savedQuestionsSig;
  const hasUnsavedChanges = settingsDirty || questionsDirty;
  const isReadOnly = exam ? exam.status !== "DRAFT" : true;

  const handleSaveSettings = async (payload: ExamCreate) => {
    if (!exam || exam.status !== "DRAFT") {
      return;
    }
    setIsSavingSettings(true);
    setSettingsError(null);
    setSettingsSuccess(null);
    setLifecycleError(null);

    try {
      const updated = await updateAdminExam(exam.id, payload);
      setExam((prev) => (prev ? { ...prev, ...updated } : null));
      setSettingsDirty(false);
      setSettingsSuccess("Exam settings saved.");
    } catch (error) {
      setSettingsError(
        extractAdminApiError(error, "Unable to save examination settings.").message,
      );
    } finally {
      setIsSavingSettings(false);
    }
  };

  const handleApplyParsedQuestions = (
    incoming: EditableQuestion[],
    mode: "append" | "replace",
  ) => {
    setQuestionsError(null);
    setQuestionsSuccess(null);
    setLifecycleError(null);
    setQuestions((prev) => (mode === "replace" ? incoming : [...prev, ...incoming]));
  };

  const handleSaveQuestions = async () => {
    if (!exam || exam.status !== "DRAFT") {
      return;
    }
    setIsSavingQuestions(true);
    setQuestionsError(null);
    setQuestionsSuccess(null);
    setLifecycleError(null);

    try {
      const payload = toQuestionCreates(questions);
      const updated = await saveExamQuestions(exam.id, payload);
      setExam(updated);
      const mapped = fromAdminQuestions(updated.questions);
      setQuestions(mapped);
      setSavedQuestionsSig(computeQuestionsSignature(mapped));
      setQuestionsSuccess(
        `Saved ${updated.questions.length} question${updated.questions.length === 1 ? "" : "s"}.`,
      );
    } catch (error) {
      setQuestionsError(
        extractAdminApiError(error, "Unable to save questions.").message,
      );
    } finally {
      setIsSavingQuestions(false);
    }
  };

  const handleDiscardQuestions = () => {
    if (!exam) {
      return;
    }
    const mapped = fromAdminQuestions(exam.questions);
    setQuestions(mapped);
    setSavedQuestionsSig(computeQuestionsSignature(mapped));
    setQuestionsError(null);
    setQuestionsSuccess(null);
  };

  const handleRequestPublish = () => {
    setLifecycleError(null);
    setLifecycleSuccess(null);
    if (hasUnsavedChanges) {
      setLifecycleError({
        message: "Save your pending settings or question edits before publishing.",
        validationErrors: [
          ...(settingsDirty ? ["Save your exam settings before publishing."] : []),
          ...(questionsDirty ? ["Save your questions before publishing."] : []),
        ],
      });
      return;
    }
    setLifecycleAction("publish");
  };

  const handleConfirmLifecycle = async () => {
    if (!exam || !lifecycleAction || isLifecyclePending) {
      return;
    }

    setIsLifecyclePending(true);
    setLifecycleError(null);
    setLifecycleSuccess(null);

    try {
      if (lifecycleAction === "publish") {
        const published = await publishAdminExam(exam.id);
        setExam((prev) => (prev ? { ...prev, ...published } : null));
        setLifecycleSuccess(
          "Examination published. Students can now view instructions and begin attempts.",
        );
      } else if (lifecycleAction === "close") {
        const closed = await closeAdminExam(exam.id);
        setExam((prev) => (prev ? { ...prev, ...closed } : null));
        setLifecycleSuccess(
          "Examination closed. New student attempts are disabled, and existing results remain available.",
        );
      } else if (lifecycleAction === "delete") {
        await deleteAdminExam(exam.id);
        navigate("/admin/exams", { replace: true });
        return;
      }
      setLifecycleAction(null);
    } catch (error) {
      setLifecycleError(
        extractAdminApiError(error, `Unable to ${lifecycleAction} examination.`),
      );
      setLifecycleAction(null);
    } finally {
      setIsLifecyclePending(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Admin Dashboard"
          title="Loading Examination"
          description="Loading exam settings and questions..."
        />
        <LoadingStatePanel label="Loading examination..." cards={2} />
      </div>
    );
  }

  if (loadError || !exam) {
    return (
      <div className="space-y-6">
        <PageHeader
          eyebrow="Admin Dashboard"
          title="Examination Unavailable"
          description="We could not open this examination."
          action={
            <Button asChild variant="outline">
              <Link to="/admin/exams">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Back to Examinations</span>
              </Link>
            </Button>
          }
        />
        <ErrorStatePanel
          title="Could not load examination"
          message={loadError ?? "Examination not found."}
          onRetry={triggerReload}
        />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Examinations"
        title={exam.title}
        description={`${exam.duration_minutes} minutes · Pass mark ${exam.pass_mark}% · ${exam.question_count} saved question${exam.question_count === 1 ? "" : "s"}`}
        action={
          <>
            <Button asChild variant="outline">
              <Link to="/admin/exams">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Examinations</span>
              </Link>
            </Button>

            <Button asChild variant="outline">
              <Link to={`/admin/exams/${exam.id}/results`}>
                <BarChart3 className="size-4" aria-hidden="true" />
                <span>Student Results</span>
              </Link>
            </Button>

            {exam.status === "DRAFT" ? (
              <>
                <Button
                  type="button"
                  variant="ghost"
                  className="text-destructive hover:bg-destructive-subtle hover:text-destructive"
                  onClick={() => {
                    setLifecycleError(null);
                    setLifecycleAction("delete");
                  }}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                  <span>Delete Draft</span>
                </Button>

                <Button type="button" onClick={handleRequestPublish}>
                  <Send className="size-4" aria-hidden="true" />
                  <span>Publish Examination</span>
                </Button>
              </>
            ) : exam.status === "PUBLISHED" ? (
              <Button
                type="button"
                variant="destructive"
                onClick={() => {
                  setLifecycleError(null);
                  setLifecycleAction("close");
                }}
              >
                <Lock className="size-4" aria-hidden="true" />
                <span>Close Examination</span>
              </Button>
            ) : null}
          </>
        }
      />

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3 text-xs text-muted-foreground">
        <div className="flex flex-wrap items-center gap-2.5">
          <ExamStatusBadge status={exam.status} />
          <span>Created: {formatDateTime(exam.created_at)}</span>
          {exam.published_at ? (
            <span>· Published: {formatDateTime(exam.published_at)}</span>
          ) : null}
          {exam.closed_at ? (
            <span>· Closed: {formatDateTime(exam.closed_at)}</span>
          ) : null}
        </div>
        {hasUnsavedChanges && exam.status === "DRAFT" ? (
          <span className="font-semibold text-warning">Unsaved draft changes</span>
        ) : null}
      </div>

      {exam.status !== "DRAFT" ? (
        <Alert variant="default" role="status">
          <div className="flex items-start gap-2.5">
            <Lock className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div>
              <AlertTitle>
                {exam.status === "PUBLISHED"
                  ? "Examination is published and locked"
                  : "Examination is closed"}
              </AlertTitle>
              <AlertDescription>
                {exam.status === "PUBLISHED"
                  ? "Published examinations cannot be edited so active student attempts and grading stay consistent. You can close the exam or review student results at any time."
                  : "Closed examinations cannot be edited or reopened, keeping existing student attempts and results intact."}
              </AlertDescription>
            </div>
          </div>
        </Alert>
      ) : null}

      {lifecycleError ? (
        <Alert variant="destructive" role="alert">
          <div className="flex items-start gap-2.5">
            <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
            <div className="min-w-0 space-y-2">
              <AlertTitle>{lifecycleError.message}</AlertTitle>
              {lifecycleError.validationErrors.length > 0 ? (
                <AlertDescription>
                  <ul className="list-disc space-y-1 pl-5">
                    {lifecycleError.validationErrors.map((err, idx) => (
                      <li key={idx}>{err}</li>
                    ))}
                  </ul>
                </AlertDescription>
              ) : null}
            </div>
          </div>
        </Alert>
      ) : null}

      {lifecycleSuccess ? (
        <Alert variant="success" role="status">
          <div className="flex items-start gap-2.5">
            <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div>
              <AlertTitle>Examination status updated</AlertTitle>
              <AlertDescription>{lifecycleSuccess}</AlertDescription>
            </div>
          </div>
        </Alert>
      ) : null}

      <nav aria-label="Examination editor sections" className="flex flex-wrap gap-2 border-b border-border pb-3">
        {(["overview", "questions", "settings"] as const).map((section) => (
          <Button
            key={section}
            type="button"
            variant={activeSection === section ? "default" : "ghost"}
            aria-current={activeSection === section ? "page" : undefined}
            onClick={() => setActiveSection(section)}
          >
            {section === "overview" ? "Overview" : section === "questions" ? `Questions (${questions.length})` : "Settings"}
          </Button>
        ))}
        <Button asChild variant="ghost">
          <Link to={`/admin/exams/${exam.id}/results`}>Results</Link>
        </Button>
      </nav>

      {activeSection === "overview" ? (
        <section aria-label="Examination overview" className="grid gap-4 rounded-lg border border-border bg-card p-5 sm:grid-cols-2 lg:grid-cols-4">
          <div><p className="text-sm text-muted-foreground">Status</p><p className="mt-1 font-semibold"><ExamStatusBadge status={exam.status} /></p></div>
          <div><p className="text-sm text-muted-foreground">Questions</p><p className="mt-1 text-xl font-semibold tabular-nums">{exam.question_count}</p></div>
          <div><p className="text-sm text-muted-foreground">Time allowed</p><p className="mt-1 text-xl font-semibold tabular-nums">{exam.duration_minutes} min</p></div>
          <div><p className="text-sm text-muted-foreground">Attempts allowed</p><p className="mt-1 text-xl font-semibold tabular-nums">{exam.max_attempts}</p></div>
          {exam.status === "DRAFT" ? <p className="sm:col-span-2 lg:col-span-4 text-sm text-muted-foreground">Prepare the questions and settings, then publish when this examination is ready for students.</p> : null}
        </section>
      ) : null}

      <div hidden={activeSection !== "settings"}>
      <ExamSettingsForm
        mode="edit"
        exam={exam}
        readOnly={isReadOnly}
        currentQuestionCount={questions.length}
        isSubmitting={isSavingSettings}
        serverError={settingsError}
        successMessage={settingsSuccess}
        onDirtyChange={setSettingsDirty}
        onSubmit={handleSaveSettings}
      />
      </div>

      <div hidden={activeSection !== "questions"} className="space-y-6">
      {!isReadOnly ? (
        <BulkParserPanel
          disabled={isReadOnly}
          existingQuestionCount={questions.length}
          onApplyQuestions={handleApplyParsedQuestions}
        />
      ) : null}

      <QuestionListEditor
        questions={questions}
        readOnly={isReadOnly}
        examStatus={exam.status}
        isDirty={questionsDirty}
        isSaving={isSavingQuestions}
        saveError={questionsError}
        saveSuccessMessage={questionsSuccess}
        onChange={(next) => {
          setQuestions(next);
          setQuestionsError(null);
          setQuestionsSuccess(null);
        }}
        onSave={handleSaveQuestions}
        onDiscard={handleDiscardQuestions}
      />
      </div>

      <ConfirmDialog
        open={lifecycleAction !== null}
        onOpenChange={(open) => {
          if (!open && !isLifecyclePending) {
            setLifecycleAction(null);
          }
        }}
        title={
          lifecycleAction === "publish"
            ? "Publish examination?"
            : lifecycleAction === "close"
              ? "Close examination?"
              : "Delete draft examination?"
        }
        description={
          lifecycleAction === "publish"
            ? `Publishing "${exam.title}" makes it available to students and locks its settings and questions so every student takes the same exam.`
            : lifecycleAction === "close"
              ? `Closing "${exam.title}" prevents students from starting new attempts. Existing student attempts and results remain available.`
              : `Permanently delete draft "${exam.title}" and all saved draft questions?`
        }
        confirmLabel={
          lifecycleAction === "publish"
            ? "Publish now"
            : lifecycleAction === "close"
              ? "Close examination"
              : "Delete draft"
        }
        confirmVariant={lifecycleAction === "publish" ? "default" : "destructive"}
        isPending={isLifecyclePending}
        onConfirm={() => void handleConfirmLifecycle()}
      />
    </div>
  );
}
