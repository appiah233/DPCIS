import {
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  CheckCircle2,
  Lock,
  Plus,
  Save,
  Trash2,
} from "lucide-react";
import { useId, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { EmptyStatePanel } from "@/components/ui/state-panel";
import { Textarea } from "@/components/ui/textarea";
import {
  OPTION_LABELS,
  createBlankEditableQuestion,
  formatDecimal,
  hasAnyQuestionValidationIssues,
  relabelSequentialOptions,
  validateEditableQuestion,
  type EditableQuestion,
} from "@/features/admin/adminUtils";
import { cn } from "@/lib/utils";

export interface QuestionListEditorProps {
  questions: EditableQuestion[];
  readOnly?: boolean;
  examStatus?: string;
  isDirty: boolean;
  isSaving: boolean;
  saveError: string | null;
  saveSuccessMessage: string | null;
  onChange: (nextQuestions: EditableQuestion[]) => void;
  onSave: () => Promise<void> | void;
  onDiscard?: () => void;
}

export function QuestionListEditor({
  questions,
  readOnly = false,
  examStatus = "DRAFT",
  isDirty,
  isSaving,
  saveError,
  saveSuccessMessage,
  onChange,
  onSave,
  onDiscard,
}: QuestionListEditorProps) {
  const baseId = useId();
  const [showValidation, setShowValidation] = useState(false);

  const totalPoints = questions.reduce((sum, q) => {
    const parsed = Number.parseFloat(q.points);
    return Number.isFinite(parsed) && parsed > 0 ? sum + parsed : sum;
  }, 0);

  const missingCorrectCount = questions.filter(
    (q) => q.options.filter((o) => o.is_correct).length !== 1,
  ).length;

  const updateQuestionAt = (
    index: number,
    updater: (current: EditableQuestion) => EditableQuestion,
  ) => {
    onChange(
      questions.map((item, idx) => (idx === index ? updater(item) : item)),
    );
  };

  const handleAddQuestion = () => {
    onChange([...questions, createBlankEditableQuestion()]);
  };

  const handleRemoveQuestion = (index: number) => {
    onChange(questions.filter((_, idx) => idx !== index));
  };

  const handleMoveQuestion = (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= questions.length) {
      return;
    }
    const copy = [...questions];
    const [moved] = copy.splice(index, 1);
    copy.splice(targetIndex, 0, moved);
    onChange(copy);
  };

  const handleSelectCorrectOption = (questionIndex: number, optionIndex: number) => {
    updateQuestionAt(questionIndex, (q) => ({
      ...q,
      parserErrors: undefined,
      options: q.options.map((opt, idx) => ({
        ...opt,
        is_correct: idx === optionIndex,
      })),
    }));
  };

  const handleAddOption = (questionIndex: number) => {
    updateQuestionAt(questionIndex, (q) => {
      if (q.options.length >= OPTION_LABELS.length) {
        return q;
      }
      const nextLabel = OPTION_LABELS[q.options.length];
      return {
        ...q,
        options: [
          ...q.options,
          { label: nextLabel, option_text: "", is_correct: false },
        ],
      };
    });
  };

  const handleRemoveOption = (questionIndex: number, optionIndex: number) => {
    updateQuestionAt(questionIndex, (q) => {
      if (q.options.length <= 2) {
        return q;
      }
      const remaining = q.options.filter((_, idx) => idx !== optionIndex);
      return {
        ...q,
        options: relabelSequentialOptions(remaining),
      };
    });
  };

  const handleSaveClick = async () => {
    if (readOnly || isSaving) {
      return;
    }
    setShowValidation(true);
    if (hasAnyQuestionValidationIssues(questions)) {
      return;
    }
    await onSave();
  };

  const hasClientIssues = hasAnyQuestionValidationIssues(questions);

  return (
    <Card as="section" id="questions-editor" aria-labelledby={`${baseId}-heading`}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle as="h2" id={`${baseId}-heading`}>
              Questions &amp; Correct Answers ({questions.length})
            </CardTitle>
            <CardDescription>
              {readOnly
                ? `Saved questions (${formatDecimal(totalPoints)} total points).`
                : `Review, reorder, or edit questions before saving (${formatDecimal(totalPoints)} total points).`}
            </CardDescription>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isDirty && !readOnly ? (
              <Badge variant="warning">Unsaved changes</Badge>
            ) : null}
            {missingCorrectCount > 0 && !readOnly ? (
              <Badge variant="destructive">
                <AlertTriangle className="size-3.5" aria-hidden="true" />
                <span>{missingCorrectCount} missing correct answer</span>
              </Badge>
            ) : null}
            {readOnly ? (
              <Badge variant="secondary">
                <Lock className="size-3.5" aria-hidden="true" />
                <span>
                  Locked (
                  {examStatus === "PUBLISHED"
                    ? "Published"
                    : examStatus === "CLOSED"
                      ? "Closed"
                      : "Draft"}
                  )
                </span>
              </Badge>
            ) : null}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {saveError ? (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Could not save questions</AlertTitle>
            <AlertDescription>{saveError}</AlertDescription>
          </Alert>
        ) : null}

        {saveSuccessMessage ? (
          <Alert variant="success" role="status">
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div>
                <AlertTitle>Questions saved</AlertTitle>
                <AlertDescription>{saveSuccessMessage}</AlertDescription>
              </div>
            </div>
          </Alert>
        ) : null}

        {showValidation && hasClientIssues && !readOnly ? (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Please resolve highlighted question issues before saving</AlertTitle>
            <AlertDescription>
              Every question requires question text, valid points, 2–4 distinct non-empty options,
              and one selected correct answer.
            </AlertDescription>
          </Alert>
        ) : null}

        {!readOnly ? (
          <div className="flex flex-wrap items-center justify-between gap-2.5">
            <Button type="button" variant="outline" disabled={isSaving} onClick={handleAddQuestion}>
              <Plus className="size-4" aria-hidden="true" />
              <span>Add Question</span>
            </Button>

            <div className="flex flex-wrap items-center gap-2">
              {isDirty && onDiscard ? (
                <Button type="button" variant="ghost" disabled={isSaving} onClick={onDiscard}>
                  Discard unsaved edits
                </Button>
              ) : null}
              <Button type="button" disabled={isSaving} onClick={() => void handleSaveClick()}>
                <Save className="size-4" aria-hidden="true" />
                <span>{isSaving ? "Saving..." : "Save Questions"}</span>
              </Button>
            </div>
          </div>
        ) : null}

        {questions.length === 0 ? (
          <EmptyStatePanel
            title="No questions in this examination yet"
            description={
              readOnly
                ? "This examination contains no saved questions."
                : "Paste questions in the box above or click Add Question to create one manually."
            }
            action={
              !readOnly ? (
                <Button type="button" onClick={handleAddQuestion}>
                  <Plus className="size-4" aria-hidden="true" />
                  <span>Add First Question</span>
                </Button>
              ) : undefined
            }
          />
        ) : (
          <ol className="space-y-4">
            {questions.map((question, qIndex) => {
              const validation = validateEditableQuestion(question);
              const hasMissingAnswer =
                question.options.filter((opt) => opt.is_correct).length !== 1;
              const shouldShowErrors =
                showValidation ||
                hasMissingAnswer ||
                Boolean(question.parserErrors && question.parserErrors.length > 0);
              const stemId = `${baseId}-stem-${question.localKey}`;
              const pointsId = `${baseId}-points-${question.localKey}`;
              const radioGroupName = `${baseId}-correct-${question.localKey}`;

              return (
                <li
                  key={question.localKey}
                  className={cn(
                    "rounded-lg border p-4 sm:p-5",
                    !readOnly && hasMissingAnswer
                      ? "border-destructive-border bg-destructive-subtle/25"
                      : "border-border bg-card",
                  )}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border pb-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold text-foreground">
                        Question {qIndex + 1}
                      </span>
                      {readOnly ? (
                        <Badge variant="outline">{formatDecimal(question.points)} pts</Badge>
                      ) : hasMissingAnswer ? (
                        <Badge variant="destructive">
                          <AlertTriangle className="size-3.5" aria-hidden="true" />
                          <span>Select correct answer</span>
                        </Badge>
                      ) : (
                        <Badge variant="success">
                          <CheckCircle2 className="size-3.5" aria-hidden="true" />
                          <span>
                            Answer:{" "}
                            {question.options.find((o) => o.is_correct)?.label ?? "—"}
                          </span>
                        </Badge>
                      )}
                    </div>

                    {!readOnly ? (
                      <div className="flex flex-wrap items-center gap-1.5">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Move Question ${qIndex + 1} up`}
                          disabled={qIndex === 0 || isSaving}
                          onClick={() => handleMoveQuestion(qIndex, -1)}
                        >
                          <ArrowUp className="size-4" aria-hidden="true" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Move Question ${qIndex + 1} down`}
                          disabled={qIndex === questions.length - 1 || isSaving}
                          onClick={() => handleMoveQuestion(qIndex, 1)}
                        >
                          <ArrowDown className="size-4" aria-hidden="true" />
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          aria-label={`Remove Question ${qIndex + 1}`}
                          disabled={isSaving}
                          onClick={() => handleRemoveQuestion(qIndex)}
                          className="text-destructive hover:bg-destructive-subtle hover:text-destructive"
                        >
                          <Trash2 className="size-4" aria-hidden="true" />
                        </Button>
                      </div>
                    ) : null}
                  </div>

                  {readOnly ? (
                    <div className="mt-3 space-y-3">
                      <p className="break-words text-base font-medium text-foreground">
                        {question.question_text}
                      </p>
                      <ul className="grid gap-2 sm:grid-cols-2">
                        {question.options.map((opt) => (
                          <li
                            key={`${question.localKey}-${opt.label}`}
                            className={cn(
                              "flex items-start justify-between gap-2 rounded-md border px-3 py-2 text-sm",
                              opt.is_correct
                                ? "border-success-border bg-success-subtle text-success"
                                : "border-border bg-background text-foreground",
                            )}
                          >
                            <span className="min-w-0 break-words">
                              <strong className="mr-1.5">{opt.label}.</strong>
                              {opt.option_text}
                            </span>
                            {opt.is_correct ? (
                              <Badge variant="success">Correct</Badge>
                            ) : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ) : (
                    <div className="mt-4 space-y-4">
                      {question.parserErrors && question.parserErrors.length > 0 ? (
                        <Alert variant="warning" role="status">
                          <AlertTitle>Needs review from pasted text</AlertTitle>
                          <AlertDescription>
                            <ul className="list-disc pl-5 text-xs">
                              {question.parserErrors.map((err, i) => (
                                <li key={i}>{err}</li>
                              ))}
                            </ul>
                          </AlertDescription>
                        </Alert>
                      ) : null}

                      <div className="grid gap-4 sm:grid-cols-[1fr_9rem]">
                        <div className="field-group space-y-1.5">
                          <Label htmlFor={stemId}>Question text</Label>
                          <Textarea
                            id={stemId}
                            rows={2}
                            disabled={isSaving}
                            value={question.question_text}
                            aria-invalid={
                              showValidation && !question.question_text.trim()
                            }
                            placeholder="Enter question text..."
                            onChange={(event) => {
                              const nextText = event.target.value;
                              updateQuestionAt(qIndex, (q) => ({
                                ...q,
                                question_text: nextText,
                              }));
                            }}
                          />
                        </div>

                        <div className="field-group space-y-1.5">
                          <Label htmlFor={pointsId}>Points</Label>
                          <Input
                            id={pointsId}
                            type="number"
                            inputMode="decimal"
                            min={0.01}
                            max={999.99}
                            step="0.25"
                            disabled={isSaving}
                            value={question.points}
                            onChange={(event) => {
                              const nextPoints = event.target.value;
                              updateQuestionAt(qIndex, (q) => ({
                                ...q,
                                points: nextPoints,
                              }));
                            }}
                          />
                        </div>
                      </div>

                      <fieldset className="space-y-2.5 border-0 p-0">
                        <legend className="text-sm font-medium text-foreground">
                          Options (select the single correct answer)
                        </legend>

                        <div className="space-y-2.5">
                          {question.options.map((opt, optIdx) => {
                            const optionInputId = `${baseId}-opt-${question.localKey}-${opt.label}`;
                            const optionRadioId = `${baseId}-radio-${question.localKey}-${opt.label}`;
                            const optError = showValidation
                              ? validation.optionErrors[optIdx]
                              : undefined;

                            return (
                              <div key={`${question.localKey}-${opt.label}`} className="space-y-1">
                                <div
                                  className={cn(
                                    "flex items-center gap-2.5 rounded-lg border p-2 transition-colors",
                                    opt.is_correct
                                      ? "border-primary bg-accent/50"
                                      : "border-border bg-background",
                                  )}
                                >
                                  <label
                                    htmlFor={optionRadioId}
                                    className="inline-flex min-h-11 min-w-11 shrink-0 cursor-pointer items-center justify-center rounded-md px-1 has-[input:focus-visible]:outline-2 has-[input:focus-visible]:outline-offset-2 has-[input:focus-visible]:outline-ring"
                                    title={`Mark Option ${opt.label} as correct`}
                                  >
                                    <input
                                      id={optionRadioId}
                                      type="radio"
                                      name={radioGroupName}
                                      checked={opt.is_correct}
                                      disabled={isSaving}
                                      aria-label={`Mark Option ${opt.label} as correct answer for Question ${qIndex + 1}`}
                                      onChange={() =>
                                        handleSelectCorrectOption(qIndex, optIdx)
                                      }
                                      className="visually-hidden"
                                    />
                                    <span
                                      aria-hidden="true"
                                      className={cn(
                                        "inline-flex size-9 items-center justify-center rounded-full border text-sm font-bold transition-colors",
                                        opt.is_correct
                                          ? "border-primary bg-primary text-primary-foreground"
                                          : "border-input bg-card text-foreground hover:border-primary",
                                      )}
                                    >
                                      {opt.label}
                                    </span>
                                  </label>

                                  <div className="min-w-0 flex-1">
                                    <Input
                                      id={optionInputId}
                                      value={opt.option_text}
                                      disabled={isSaving}
                                      aria-label={`Option ${opt.label} text for Question ${qIndex + 1}`}
                                      aria-invalid={Boolean(optError)}
                                      placeholder={`Option ${opt.label} text`}
                                      onChange={(event) => {
                                        const nextVal = event.target.value;
                                        updateQuestionAt(qIndex, (q) => ({
                                          ...q,
                                          options: q.options.map((item, idx) =>
                                            idx === optIdx
                                              ? { ...item, option_text: nextVal }
                                              : item,
                                          ),
                                        }));
                                      }}
                                    />
                                  </div>

                                  {question.options.length > 2 ? (
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      size="icon"
                                      disabled={isSaving}
                                      aria-label={`Remove Option ${opt.label} from Question ${qIndex + 1}`}
                                      onClick={() => handleRemoveOption(qIndex, optIdx)}
                                    >
                                      <Trash2 className="size-4" aria-hidden="true" />
                                    </Button>
                                  ) : null}
                                </div>

                                {optError ? (
                                  <p className="pl-2 text-xs font-medium text-destructive">
                                    {optError}
                                  </p>
                                ) : null}
                              </div>
                            );
                          })}
                        </div>

                        {question.options.length < OPTION_LABELS.length ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            disabled={isSaving}
                            onClick={() => handleAddOption(qIndex)}
                          >
                            <Plus className="size-4" aria-hidden="true" />
                            <span>
                              Add Option {OPTION_LABELS[question.options.length]}
                            </span>
                          </Button>
                        ) : null}
                      </fieldset>

                      {shouldShowErrors && validation.questionErrors.length > 0 ? (
                        <ul className="list-disc space-y-0.5 pl-5 text-xs font-medium text-destructive">
                          {validation.questionErrors.map((err, errIdx) => (
                            <li key={errIdx}>{err}</li>
                          ))}
                        </ul>
                      ) : null}
                    </div>
                  )}
                </li>
              );
            })}
          </ol>
        )}
      </CardContent>

      {!readOnly && questions.length > 0 ? (
        <CardFooter className="justify-between">
          <Button type="button" variant="outline" disabled={isSaving} onClick={handleAddQuestion}>
            <Plus className="size-4" aria-hidden="true" />
            <span>Add Question</span>
          </Button>
          <Button type="button" disabled={isSaving} onClick={() => void handleSaveClick()}>
            <Save className="size-4" aria-hidden="true" />
            <span>{isSaving ? "Saving..." : "Save Questions"}</span>
          </Button>
        </CardFooter>
      ) : null}
    </Card>
  );
}
