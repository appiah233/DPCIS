import { AlertTriangle, CheckCircle2, Lock, Save } from "lucide-react";
import { useEffect, useId, useMemo, useState, type FormEvent } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ExamAdminOut, ExamCreate } from "@/types/adminExam";

interface SettingsFormValues {
  title: string;
  description: string;
  instructions: string;
  durationMinutes: string;
  passMark: string;
  questionLimit: string;
  maxAttempts: string;
  randomizeQuestions: boolean;
  randomizeOptions: boolean;
  showResult: boolean;
  showCorrectAnswers: boolean;
}

type FieldErrorKey =
  | "title"
  | "description"
  | "instructions"
  | "durationMinutes"
  | "passMark"
  | "questionLimit"
  | "maxAttempts"
  | "showCorrectAnswers";

function toFormValues(exam?: ExamAdminOut | null): SettingsFormValues {
  if (!exam) {
    return {
      title: "",
      description: "",
      instructions: "",
      durationMinutes: "45",
      passMark: "50",
      questionLimit: "",
      maxAttempts: "1",
      randomizeQuestions: false,
      randomizeOptions: false,
      showResult: true,
      showCorrectAnswers: false,
    };
  }

  return {
    title: exam.title,
    description: exam.description ?? "",
    instructions: exam.instructions ?? "",
    durationMinutes: String(exam.duration_minutes),
    passMark: String(exam.pass_mark),
    questionLimit: exam.question_limit === null ? "" : String(exam.question_limit),
    maxAttempts: String(exam.max_attempts),
    randomizeQuestions: exam.randomize_questions,
    randomizeOptions: exam.randomize_options,
    showResult: exam.show_result,
    showCorrectAnswers: exam.show_result ? exam.show_correct_answers : false,
  };
}

function validateFormValues(
  values: SettingsFormValues,
): Partial<Record<FieldErrorKey, string>> {
  const errors: Partial<Record<FieldErrorKey, string>> = {};

  const trimmedTitle = values.title.trim();
  if (!trimmedTitle) {
    errors.title = "Examination title is required.";
  } else if (trimmedTitle.length > 200) {
    errors.title = "Title must be 200 characters or fewer.";
  }

  if (values.description.trim().length > 2000) {
    errors.description = "Description must be 2000 characters or fewer.";
  }

  if (values.instructions.trim().length > 4000) {
    errors.instructions = "Instructions must be 4000 characters or fewer.";
  }

  const duration = Number(values.durationMinutes);
  if (!values.durationMinutes.trim() || !Number.isInteger(duration) || duration < 1) {
    errors.durationMinutes = "Duration must be a whole number of at least 1 minute.";
  }

  const passMarkTrimmed = values.passMark.trim();
  const passMarkNum = Number.parseFloat(passMarkTrimmed);
  if (
    !passMarkTrimmed ||
    !Number.isFinite(passMarkNum) ||
    passMarkNum < 0 ||
    passMarkNum > 100
  ) {
    errors.passMark = "Pass mark must be between 0 and 100.";
  } else if (!/^\d+(\.\d{1,2})?$/.test(passMarkTrimmed)) {
    errors.passMark = "Pass mark may have at most 2 decimal places.";
  }

  if (values.questionLimit.trim()) {
    const limit = Number(values.questionLimit);
    if (!Number.isInteger(limit) || limit < 1) {
      errors.questionLimit = "Question limit must be a whole number of at least 1, or blank for all.";
    }
  }

  const maxAttempts = Number(values.maxAttempts);
  if (!values.maxAttempts.trim() || !Number.isInteger(maxAttempts) || maxAttempts < 1) {
    errors.maxAttempts = "Max attempts must be a whole number of at least 1.";
  }

  if (!values.showResult && values.showCorrectAnswers) {
    errors.showCorrectAnswers =
      "Cannot show correct answers when result display is disabled.";
  }

  return errors;
}

export interface ExamSettingsFormProps {
  mode: "create" | "edit";
  exam?: ExamAdminOut | null;
  readOnly?: boolean;
  currentQuestionCount?: number;
  isSubmitting?: boolean;
  serverError?: string | null;
  successMessage?: string | null;
  onDirtyChange?: (dirty: boolean) => void;
  onSubmit: (payload: ExamCreate) => Promise<void> | void;
}

export function ExamSettingsForm({
  mode,
  exam = null,
  readOnly = false,
  currentQuestionCount,
  isSubmitting = false,
  serverError = null,
  successMessage = null,
  onDirtyChange,
  onSubmit,
}: ExamSettingsFormProps) {
  const baseId = useId();
  const [values, setValues] = useState<SettingsFormValues>(() => toFormValues(exam));
  const [fieldErrors, setFieldErrors] = useState<Partial<Record<FieldErrorKey, string>>>({});

  const baselineSignature = useMemo(() => JSON.stringify(toFormValues(exam)), [exam]);

  useEffect(() => {
    setValues(toFormValues(exam));
    setFieldErrors({});
  }, [exam]);

  const isDirty = useMemo(
    () => JSON.stringify(values) !== baselineSignature,
    [values, baselineSignature],
  );

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  const parsedQuestionLimit = values.questionLimit.trim()
    ? Number(values.questionLimit)
    : null;
  const limitExceedsQuestions =
    typeof currentQuestionCount === "number" &&
    currentQuestionCount > 0 &&
    parsedQuestionLimit !== null &&
    Number.isInteger(parsedQuestionLimit) &&
    parsedQuestionLimit > currentQuestionCount;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (readOnly || isSubmitting) {
      return;
    }

    const validationErrors = validateFormValues(values);
    setFieldErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      return;
    }

    const payload: ExamCreate = {
      title: values.title.trim(),
      description: values.description.trim() || null,
      instructions: values.instructions.trim() || null,
      duration_minutes: Number(values.durationMinutes),
      pass_mark: Number.parseFloat(values.passMark).toFixed(2),
      question_limit: values.questionLimit.trim()
        ? Number(values.questionLimit)
        : null,
      randomize_questions: values.randomizeQuestions,
      randomize_options: values.randomizeOptions,
      max_attempts: Number(values.maxAttempts),
      show_result: values.showResult,
      show_correct_answers: values.showResult ? values.showCorrectAnswers : false,
    };

    await onSubmit(payload);
  };

  const isDisabled = readOnly || isSubmitting;

  const titleId = `${baseId}-title`;
  const titleErrorId = `${baseId}-title-err`;
  const descId = `${baseId}-desc`;
  const descErrorId = `${baseId}-desc-err`;
  const instrId = `${baseId}-instr`;
  const instrErrorId = `${baseId}-instr-err`;
  const durationId = `${baseId}-duration`;
  const durationErrorId = `${baseId}-duration-err`;
  const passMarkId = `${baseId}-pass-mark`;
  const passMarkErrorId = `${baseId}-pass-mark-err`;
  const questionLimitId = `${baseId}-question-limit`;
  const questionLimitHelpId = `${baseId}-question-limit-help`;
  const questionLimitErrorId = `${baseId}-question-limit-err`;
  const maxAttemptsId = `${baseId}-max-attempts`;
  const maxAttemptsErrorId = `${baseId}-max-attempts-err`;

  return (
    <Card as="section" aria-labelledby={`${baseId}-heading`}>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <CardTitle as="h2" id={`${baseId}-heading`}>
              {mode === "create" ? "Examination Details & Settings" : "Exam Settings"}
            </CardTitle>
            <CardDescription>
              Set the timing, pass mark, question order, attempt limit, and what students see
              after finishing.
            </CardDescription>
          </div>
          {readOnly ? (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-border bg-muted px-3 py-1 text-xs font-medium text-muted-foreground">
              <Lock className="size-3.5" aria-hidden="true" />
              <span>Locked ({exam?.status === "PUBLISHED" ? "Published" : "Closed"})</span>
            </span>
          ) : null}
        </div>
      </CardHeader>

      <form onSubmit={handleSubmit} noValidate>
        <CardContent className="space-y-5">
          {serverError ? (
            <Alert variant="destructive" role="alert">
              <AlertTitle>Could not save examination settings</AlertTitle>
              <AlertDescription>{serverError}</AlertDescription>
            </Alert>
          ) : null}

          {successMessage ? (
            <Alert variant="success" role="status">
              <div className="flex items-start gap-2.5">
                <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <div>
                  <AlertTitle>Settings saved</AlertTitle>
                  <AlertDescription>{successMessage}</AlertDescription>
                </div>
              </div>
            </Alert>
          ) : null}

          <div className="field-group space-y-1.5">
            <Label htmlFor={titleId}>
              Examination title <span className="text-destructive">*</span>
            </Label>
            <Input
              id={titleId}
              name="title"
              required
              maxLength={200}
              disabled={isDisabled}
              value={values.title}
              aria-invalid={Boolean(fieldErrors.title)}
              aria-describedby={fieldErrors.title ? titleErrorId : undefined}
              placeholder="e.g. Introduction to Computer Networking — Midterm"
              onChange={(event) => {
                setValues((prev) => ({ ...prev, title: event.target.value }));
                setFieldErrors((prev) => ({ ...prev, title: undefined }));
              }}
            />
            {fieldErrors.title ? (
              <p id={titleErrorId} className="text-xs font-medium text-destructive">
                {fieldErrors.title}
              </p>
            ) : null}
          </div>

          <div className="field-group space-y-1.5">
            <Label htmlFor={descId}>Description</Label>
            <Textarea
              id={descId}
              name="description"
              maxLength={2000}
              disabled={isDisabled}
              value={values.description}
              aria-invalid={Boolean(fieldErrors.description)}
              aria-describedby={fieldErrors.description ? descErrorId : undefined}
              placeholder="Short summary shown to candidates in the available examinations list."
              onChange={(event) => {
                setValues((prev) => ({ ...prev, description: event.target.value }));
                setFieldErrors((prev) => ({ ...prev, description: undefined }));
              }}
            />
            {fieldErrors.description ? (
              <p id={descErrorId} className="text-xs font-medium text-destructive">
                {fieldErrors.description}
              </p>
            ) : null}
          </div>

          <div className="field-group space-y-1.5">
            <Label htmlFor={instrId}>Candidate instructions</Label>
            <Textarea
              id={instrId}
              name="instructions"
              maxLength={4000}
              disabled={isDisabled}
              value={values.instructions}
              aria-invalid={Boolean(fieldErrors.instructions)}
              aria-describedby={fieldErrors.instructions ? instrErrorId : undefined}
              placeholder="Rules displayed on the pre-exam instructions screen before the timer begins."
              onChange={(event) => {
                setValues((prev) => ({ ...prev, instructions: event.target.value }));
                setFieldErrors((prev) => ({ ...prev, instructions: undefined }));
              }}
            />
            {fieldErrors.instructions ? (
              <p id={instrErrorId} className="text-xs font-medium text-destructive">
                {fieldErrors.instructions}
              </p>
            ) : null}
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="field-group space-y-1.5">
              <Label htmlFor={durationId}>
                Duration (minutes) <span className="text-destructive">*</span>
              </Label>
              <Input
                id={durationId}
                name="duration_minutes"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                required
                disabled={isDisabled}
                value={values.durationMinutes}
                aria-invalid={Boolean(fieldErrors.durationMinutes)}
                aria-describedby={fieldErrors.durationMinutes ? durationErrorId : undefined}
                onChange={(event) => {
                  setValues((prev) => ({ ...prev, durationMinutes: event.target.value }));
                  setFieldErrors((prev) => ({ ...prev, durationMinutes: undefined }));
                }}
              />
              {fieldErrors.durationMinutes ? (
                <p id={durationErrorId} className="text-xs font-medium text-destructive">
                  {fieldErrors.durationMinutes}
                </p>
              ) : null}
            </div>

            <div className="field-group space-y-1.5">
              <Label htmlFor={passMarkId}>
                Pass mark (%) <span className="text-destructive">*</span>
              </Label>
              <Input
                id={passMarkId}
                name="pass_mark"
                type="number"
                inputMode="decimal"
                min={0}
                max={100}
                step="0.01"
                required
                disabled={isDisabled}
                value={values.passMark}
                aria-invalid={Boolean(fieldErrors.passMark)}
                aria-describedby={fieldErrors.passMark ? passMarkErrorId : undefined}
                onChange={(event) => {
                  setValues((prev) => ({ ...prev, passMark: event.target.value }));
                  setFieldErrors((prev) => ({ ...prev, passMark: undefined }));
                }}
              />
              {fieldErrors.passMark ? (
                <p id={passMarkErrorId} className="text-xs font-medium text-destructive">
                  {fieldErrors.passMark}
                </p>
              ) : null}
            </div>

            <div className="field-group space-y-1.5">
              <Label htmlFor={questionLimitId}>Question limit per attempt (optional)</Label>
              <Input
                id={questionLimitId}
                name="question_limit"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                disabled={isDisabled}
                value={values.questionLimit}
                placeholder="All saved questions"
                aria-invalid={Boolean(fieldErrors.questionLimit)}
                aria-describedby={
                  fieldErrors.questionLimit ? questionLimitErrorId : questionLimitHelpId
                }
                onChange={(event) => {
                  setValues((prev) => ({ ...prev, questionLimit: event.target.value }));
                  setFieldErrors((prev) => ({ ...prev, questionLimit: undefined }));
                }}
              />
              {fieldErrors.questionLimit ? (
                <p id={questionLimitErrorId} className="text-xs font-medium text-destructive">
                  {fieldErrors.questionLimit}
                </p>
              ) : (
                <p id={questionLimitHelpId} className="text-xs text-muted-foreground">
                  Leave blank to deliver all saved questions to every student.
                </p>
              )}
            </div>

            <div className="field-group space-y-1.5">
              <Label htmlFor={maxAttemptsId}>
                Max attempts per student <span className="text-destructive">*</span>
              </Label>
              <Input
                id={maxAttemptsId}
                name="max_attempts"
                type="number"
                inputMode="numeric"
                min={1}
                step={1}
                required
                disabled={isDisabled}
                value={values.maxAttempts}
                aria-invalid={Boolean(fieldErrors.maxAttempts)}
                aria-describedby={fieldErrors.maxAttempts ? maxAttemptsErrorId : undefined}
                onChange={(event) => {
                  setValues((prev) => ({ ...prev, maxAttempts: event.target.value }));
                  setFieldErrors((prev) => ({ ...prev, maxAttempts: undefined }));
                }}
              />
              {fieldErrors.maxAttempts ? (
                <p id={maxAttemptsErrorId} className="text-xs font-medium text-destructive">
                  {fieldErrors.maxAttempts}
                </p>
              ) : null}
            </div>
          </div>

          {limitExceedsQuestions ? (
            <Alert variant="warning" role="status">
              <div className="flex items-start gap-2.5">
                <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                <div>
                  <AlertTitle>Question limit exceeds saved questions</AlertTitle>
                  <AlertDescription>
                    Question limit ({parsedQuestionLimit}) is greater than the{" "}
                    {currentQuestionCount} saved question{currentQuestionCount === 1 ? "" : "s"}.
                    Add more questions or lower the limit before publishing.
                  </AlertDescription>
                </div>
              </div>
            </Alert>
          ) : null}

          <fieldset className="space-y-3 border-0 p-0">
            <legend className="text-sm font-semibold text-foreground">
              Question Order &amp; Student Results
            </legend>

            <div className="grid gap-3 sm:grid-cols-2">
              <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-border bg-card p-3.5 transition-colors hover:bg-muted/40">
                <input
                  type="checkbox"
                  checked={values.randomizeQuestions}
                  disabled={isDisabled}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      randomizeQuestions: event.target.checked,
                    }))
                  }
                  className="mt-0.5 size-5 shrink-0 accent-primary"
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="block text-sm font-medium text-foreground">
                    Randomize question order
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    Gives each student a shuffled question order.
                  </span>
                </span>
              </label>

              <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-border bg-card p-3.5 transition-colors hover:bg-muted/40">
                <input
                  type="checkbox"
                  checked={values.randomizeOptions}
                  disabled={isDisabled}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      randomizeOptions: event.target.checked,
                    }))
                  }
                  className="mt-0.5 size-5 shrink-0 accent-primary"
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="block text-sm font-medium text-foreground">
                    Randomize option order
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    Shuffles choices A–D for each student.
                  </span>
                </span>
              </label>

              <label className="flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border border-border bg-card p-3.5 transition-colors hover:bg-muted/40">
                <input
                  type="checkbox"
                  checked={values.showResult}
                  disabled={isDisabled}
                  onChange={(event) => {
                    const checked = event.target.checked;
                    setValues((prev) => ({
                      ...prev,
                      showResult: checked,
                      showCorrectAnswers: checked ? prev.showCorrectAnswers : false,
                    }));
                    setFieldErrors((prev) => ({ ...prev, showCorrectAnswers: undefined }));
                  }}
                  className="mt-0.5 size-5 shrink-0 accent-primary"
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="block text-sm font-medium text-foreground">
                    Show score &amp; outcome to students
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    Students see their percentage score and pass/fail result after submitting.
                  </span>
                </span>
              </label>

              <label
                className={`flex min-h-11 items-start gap-3 rounded-lg border border-border bg-card p-3.5 transition-colors ${
                  !values.showResult || isDisabled
                    ? "cursor-not-allowed bg-muted/40 opacity-75"
                    : "cursor-pointer hover:bg-muted/40"
                }`}
              >
                <input
                  type="checkbox"
                  checked={values.showResult && values.showCorrectAnswers}
                  disabled={isDisabled || !values.showResult}
                  onChange={(event) =>
                    setValues((prev) => ({
                      ...prev,
                      showCorrectAnswers: event.target.checked,
                    }))
                  }
                  className="mt-0.5 size-5 shrink-0 accent-primary"
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="block text-sm font-medium text-foreground">
                    Show correct answers after submission
                  </span>
                  <span className="block text-xs text-muted-foreground">
                    {values.showResult
                      ? "Shows the correct answers after a student submits."
                      : "Enable 'Show score & outcome to students' first."}
                  </span>
                </span>
              </label>
            </div>
          </fieldset>
        </CardContent>

        {!readOnly ? (
          <CardFooter className="justify-between">
            <span className="text-xs text-muted-foreground">
              {mode === "create"
                ? "New examinations begin in Draft mode until you add questions and publish."
                : isDirty
                  ? "You have unsaved configuration changes."
                  : "Settings match the saved draft."}
            </span>

            <Button type="submit" disabled={isSubmitting || (mode === "edit" && !isDirty)}>
              <Save className="size-4" aria-hidden="true" />
              <span>
                {isSubmitting
                  ? "Saving..."
                  : mode === "create"
                    ? "Create Draft Exam"
                    : "Save Settings"}
              </span>
            </Button>
          </CardFooter>
        ) : null}
      </form>
    </Card>
  );
}
