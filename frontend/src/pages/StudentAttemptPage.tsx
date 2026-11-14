import { AlertTriangle, ArrowLeft, LayoutGrid, RotateCcw, X } from "lucide-react";
import { useCallback, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { ExamProgressHeader } from "@/components/exam/ExamProgressHeader";
import { ExamTimerBadge } from "@/components/exam/ExamTimerBadge";
import { McqQuestionCard } from "@/components/exam/McqQuestionCard";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/dialog";
import { QuestionTile } from "@/components/ui/question-tile";
import { ErrorStatePanel, LoadingStatePanel } from "@/components/ui/state-panel";
import { QuestionNavigatorDialog } from "@/features/student/QuestionNavigatorDialog";
import { formatDurationMinutes } from "@/features/student/formatters";
import { useAttemptRunner } from "@/features/student/useAttemptRunner";

export function StudentAttemptPage() {
  const { attemptId } = useParams<{ attemptId: string }>();
  const {
    status,
    delivery,
    loadError,
    currentIndex,
    setCurrentIndex,
    answers,
    saveStatus,
    saveMessage,
    failedSave,
    dismissFailedSave,
    retryFailedSave,
    selectOption,
    isLocked,
    isSubmitting,
    isExpired,
    submitError,
    submitNow,
    reload,
  } = useAttemptRunner(attemptId);

  const [isNavigatorOpen, setIsNavigatorOpen] = useState(false);
  const [isSubmitDialogOpen, setIsSubmitDialogOpen] = useState(false);
  const questionHeadingRef = useRef<HTMLHeadingElement>(null);

  const navigateToQuestion = useCallback(
    (nextIndex: number) => {
      setCurrentIndex(nextIndex);
      window.requestAnimationFrame(() => {
        questionHeadingRef.current?.focus();
      });
    },
    [setCurrentIndex],
  );

  const handleTimerExpire = useCallback(() => {
    setIsSubmitDialogOpen(false);
    setIsNavigatorOpen(false);
    void submitNow("expired");
  }, [submitNow]);

  if (status === "loading") {
    return (
      <div className="space-y-6">
        <h1
          tabIndex={-1}
          className="text-xl font-bold tracking-tight text-foreground outline-none sm:text-2xl"
        >
          Loading Examination Session
        </h1>
        <LoadingStatePanel label="Restoring examination questions and saved answers..." cards={1} />
      </div>
    );
  }

  if (status === "error" || !delivery) {
    return (
      <div className="space-y-6">
        <h1
          tabIndex={-1}
          className="text-xl font-bold tracking-tight text-foreground outline-none sm:text-2xl"
        >
          Examination Session Unavailable
        </h1>
        <ErrorStatePanel
          title="Could not load this examination attempt"
          message={loadError ?? "We could not open this examination sitting right now."}
          onRetry={reload}
          action={
            <Button asChild variant="outline">
              <Link to="/student">
                <ArrowLeft className="size-4" aria-hidden="true" />
                <span>Back to dashboard</span>
              </Link>
            </Button>
          }
        />
      </div>
    );
  }

  const questions = delivery.questions;
  const totalQuestions = questions.length;
  const currentQuestion = questions[currentIndex];
  const answeredCount = questions.reduce(
    (count, question) => (answers[question.id] ? count + 1 : count),
    0,
  );
  const unansweredCount = Math.max(0, totalQuestions - answeredCount);
  const currentSelection = currentQuestion ? (answers[currentQuestion.id] ?? null) : null;

  return (
    <div className="student-attempt-page student-attempt-grid">
      <div className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border bg-card px-4 py-3.5 shadow-xs sm:px-5">
        <div className="min-w-0 space-y-0.5">
          <h1
            tabIndex={-1}
            className="break-words text-xl font-bold tracking-tight text-foreground outline-none sm:text-2xl"
          >
            {delivery.exam_title}
          </h1>
          <p className="text-xs text-muted-foreground tabular-nums sm:text-sm">
            {formatDurationMinutes(delivery.duration_minutes)} · {totalQuestions}{" "}
            {totalQuestions === 1 ? "question" : "questions"}
          </p>
        </div>

        <ExamTimerBadge
          expiresAt={delivery.expires_at}
          serverNow={delivery.server_now}
          onExpire={handleTimerExpire}
        />
      </div>

      <ExamProgressHeader
        currentIndex={currentIndex}
        totalQuestions={totalQuestions}
        answeredCount={answeredCount}
        saveStatus={saveStatus}
        saveMessage={saveMessage}
      />

      {isExpired ? (
        <Alert variant="warning" role="status">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-start gap-2.5">
              <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
              <div>
                <AlertTitle>Examination time has expired</AlertTitle>
                <AlertDescription>
                  {isSubmitting
                    ? "Submitting your recorded answers..."
                    : "Answer changes are locked. Select Finalize & Continue to complete your sitting."}
                </AlertDescription>
              </div>
            </div>
            {!isSubmitting ? (
              <Button type="button" variant="default" onClick={() => void submitNow("expired")}>
                <span>Finalize &amp; Continue</span>
              </Button>
            ) : null}
          </div>
        </Alert>
      ) : null}

      {submitError ? (
        <Alert variant="destructive" role="alert">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 space-y-1">
              <AlertTitle>Submission interrupted</AlertTitle>
              <AlertDescription>{submitError}</AlertDescription>
            </div>
            <Button
              type="button"
              variant="outline"
              onClick={() => void submitNow(isExpired ? "expired" : "manual")}
              disabled={isSubmitting}
            >
              <RotateCcw className="size-4" aria-hidden="true" />
              <span>Retry Submission</span>
            </Button>
          </div>
        </Alert>
      ) : null}

      {failedSave ? (
        <Alert variant="destructive" role="alert">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0 space-y-1">
              <AlertTitle>
                Could not save Question {failedSave.questionNumber}
                {failedSave.attemptedLabel ? ` (Option ${failedSave.attemptedLabel})` : ""}
              </AlertTitle>
              <AlertDescription>
                {failedSave.message} Your previous saved answer has been restored.
              </AlertDescription>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              <Button type="button" variant="outline" onClick={retryFailedSave} disabled={isLocked}>
                <RotateCcw className="size-4" aria-hidden="true" />
                <span>Retry Save</span>
              </Button>
              <Button
                type="button"
                variant="ghost"
                aria-label="Dismiss save error"
                onClick={dismissFailedSave}
              >
                <X className="size-4" aria-hidden="true" />
                <span>Dismiss</span>
              </Button>
            </div>
          </div>
        </Alert>
      ) : null}

      {currentQuestion ? (
        <>
          <McqQuestionCard
            questionNumber={currentIndex + 1}
            totalQuestions={totalQuestions}
            questionText={currentQuestion.question_text}
            imageUrls={currentQuestion.image_urls}
            points={currentQuestion.points}
            options={currentQuestion.options.map((opt) => ({
              optionId: opt.id,
              label: opt.label,
              optionText: opt.option_text,
            }))}
            selectedOptionId={currentSelection}
            onSelectOption={(optionId) => selectOption(currentQuestion.id, optionId)}
            disabled={isLocked}
            onPrevious={() => navigateToQuestion(currentIndex - 1)}
            onNext={() => navigateToQuestion(currentIndex + 1)}
            canGoPrevious={currentIndex > 0}
            canGoNext={currentIndex < totalQuestions - 1}
            onRequestSubmit={() => setIsSubmitDialogOpen(true)}
            isSubmitting={isSubmitting}
            submitLabel="Review & Submit"
            headingRef={questionHeadingRef}
          />

          <div className="flex flex-wrap items-center justify-between gap-2">
            {currentSelection && !isLocked ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => selectOption(currentQuestion.id, null)}
              >
                Clear selection
              </Button>
            ) : (
              <span />
            )}

            <Button
              type="button"
              variant="outline"
              aria-label={`Open question navigator (${answeredCount} of ${totalQuestions} answered)`}
              onClick={() => setIsNavigatorOpen(true)}
            >
              <LayoutGrid className="size-4" aria-hidden="true" />
              <span className="tabular-nums">
                Question navigator ({answeredCount}/{totalQuestions})
              </span>
            </Button>
          </div>
        </>
      ) : (
        <ErrorStatePanel
          title="No questions available in this attempt"
          message="This examination session returned zero questions."
          action={
            <Button asChild variant="outline">
              <Link to="/student">Return to dashboard</Link>
            </Button>
          }
        />
      )}

      </div>

      <aside aria-label="Question progress" className="student-card student-question-map">
        <div className="student-card-heading"><h2>Question map</h2><span className="text-xs text-muted-foreground">{answeredCount} answered</span></div>
        <div className="student-question-map-grid">
          {questions.map((question, index) => {
            const isAnswered = Boolean(answers[question.id]);
            const isCurrent = index === currentIndex;
            return (
              <QuestionTile
                key={question.id}
                questionNumber={index + 1}
                isCurrent={isCurrent}
                isAnswered={isAnswered}
                variant="grid"
                onClick={() => navigateToQuestion(index)}
              />
            );
          })}
        </div>
        <div className="border-t border-border p-4"><Button variant="outline" className="w-full" onClick={() => setIsSubmitDialogOpen(true)}>Review before submitting</Button></div>
      </aside>

      <div className="student-mobile-controls"><Button variant="outline" disabled={currentIndex === 0 || isLocked} onClick={() => navigateToQuestion(currentIndex - 1)}>Previous</Button><Button variant="outline" onClick={() => setIsNavigatorOpen(true)} aria-label="Open question map"><LayoutGrid className="size-4" />{currentIndex + 1} of {totalQuestions}</Button>{currentIndex < totalQuestions - 1 ? <Button disabled={isLocked} onClick={() => navigateToQuestion(currentIndex + 1)}>Next</Button> : <Button disabled={isLocked} onClick={() => setIsSubmitDialogOpen(true)}>Review</Button>}</div>

      <QuestionNavigatorDialog
        open={isNavigatorOpen}
        onOpenChange={setIsNavigatorOpen}
        questions={questions}
        answers={answers}
        currentIndex={currentIndex}
        onSelectIndex={navigateToQuestion}
      />

      <ConfirmDialog
        open={isSubmitDialogOpen}
        onOpenChange={setIsSubmitDialogOpen}
        title="Review & Submit Examination?"
        description="Once submitted, your answers are locked and cannot be changed."
        confirmLabel="Submit Examination"
        cancelLabel="Return to Exam"
        isPending={isSubmitting}
        onConfirm={() => {
          setIsSubmitDialogOpen(false);
          void submitNow("manual");
        }}
      >
        <div className="space-y-4">
          <dl className="grid grid-cols-1 gap-2.5 rounded-lg border border-border bg-muted/40 p-3.5 text-sm sm:grid-cols-3 sm:text-center">
            <div className="flex items-center justify-between gap-2 sm:block">
              <dt className="text-xs text-muted-foreground">Total</dt>
              <dd className="font-semibold tabular-nums text-foreground sm:mt-0.5">
                {totalQuestions}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2 sm:block">
              <dt className="text-xs text-muted-foreground">Answered</dt>
              <dd className="font-semibold tabular-nums text-success sm:mt-0.5">
                {answeredCount}
              </dd>
            </div>
            <div className="flex items-center justify-between gap-2 sm:block">
              <dt className="text-xs text-muted-foreground">Unanswered</dt>
              <dd className="font-semibold tabular-nums text-foreground sm:mt-0.5">
                {unansweredCount}
              </dd>
            </div>
          </dl>

          {unansweredCount > 0 ? (
            <Alert variant="warning">
              <AlertTitle>Unanswered questions remain</AlertTitle>
              <AlertDescription>
                You still have {unansweredCount}{" "}
                {unansweredCount === 1 ? "question" : "questions"} without a selected option.
              </AlertDescription>
            </Alert>
          ) : null}

          {failedSave ? (
            <Alert variant="destructive">
              <AlertTitle>Pending save failure on Question {failedSave.questionNumber}</AlertTitle>
              <AlertDescription>
                Your last click on Question {failedSave.questionNumber} did not save. Return to the
                exam to retry saving before submitting.
              </AlertDescription>
            </Alert>
          ) : null}
        </div>
      </ConfirmDialog>
    </div>
  );
}
