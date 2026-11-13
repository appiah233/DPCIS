import {
  AlertTriangle,
  CheckCircle2,
  ClipboardPaste,
  FilePlus2,
  ListChecks,
  Replace,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useId, useMemo, useState } from "react";

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
import { ConfirmDialog } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { parseQuestions } from "@/features/admin/adminApi";
import {
  extractAdminApiError,
  fromParsedQuestion,
  type EditableQuestion,
} from "@/features/admin/adminUtils";
import { cn } from "@/lib/utils";
import type { ParsedQuestion, ParseQuestionsResponse } from "@/types/adminExam";

const SAMPLE_FORMAT_TEXT = `1. Which protocol secures HTTP traffic using TLS?
A. FTP
B. HTTPS
C. Telnet
D. SMTP
ANSWER: B

2. Which status code indicates a newly created resource?
A. 200 OK
B. 201 Created
C. 404 Not Found
D. 409 Conflict
ANSWER: B`;

const MAX_IMPORT_FILE_BYTES = 100 * 1024 * 1024;

export interface BulkParserPanelProps {
  disabled?: boolean;
  existingQuestionCount: number;
  onApplyQuestions: (questions: EditableQuestion[], mode: "append" | "replace") => void;
}

export function BulkParserPanel({
  disabled = false,
  existingQuestionCount,
  onApplyQuestions,
}: BulkParserPanelProps) {
  const baseId = useId();
  const textareaId = `${baseId}-raw-text`;
  const answerKeyId = `${baseId}-answer-key`;
  const helpId = `${baseId}-format-help`;

  const [rawText, setRawText] = useState("");
  const [answerKeyText, setAnswerKeyText] = useState("");
  const [activeInput, setActiveInput] = useState<"questions" | "answers">("questions");
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [isReadingFile, setIsReadingFile] = useState(false);
  const [isParsing, setIsParsing] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [parseResult, setParseResult] = useState<ParseQuestionsResponse | null>(null);
  const [appliedBanner, setAppliedBanner] = useState<string | null>(null);
  const [confirmReplaceMode, setConfirmReplaceMode] = useState<"valid" | "all" | null>(null);

  const orderedBlocks = useMemo<ParsedQuestion[]>(() => {
    if (!parseResult) {
      return [];
    }
    return [...parseResult.valid_questions, ...parseResult.invalid_questions].sort(
      (a, b) => a.position - b.position,
    );
  }, [parseResult]);

  const loadTextFile = async (file: File | undefined, kind: "questions" | "answers") => {
    if (!file || disabled || isParsing || isReadingFile) return;
    if (!/\.(txt|md)$/i.test(file.name) || file.size > MAX_IMPORT_FILE_BYTES) {
      setRequestError("Choose a .txt or .md file up to 100 MB.");
      return;
    }
    setIsReadingFile(true);
    try {
      const contents = await file.text();
      if (!contents.trim()) throw new Error("The selected file is empty.");
      if (kind === "questions") setRawText(contents);
      else setAnswerKeyText(contents);
      setParseResult(null);
      setAppliedBanner(null);
      setRequestError(null);
    } catch {
      setRequestError("The file could not be read. Please try another text file.");
    } finally {
      setIsReadingFile(false);
    }
  };

  const handleParse = async () => {
    if (disabled || isParsing || isReadingFile) {
      return;
    }

    setIsParsing(true);
    setRequestError(null);
    setAppliedBanner(null);

    try {
      const response = await parseQuestions(rawText, answerKeyText);
      setParseResult(response);
    } catch (error) {
      setRequestError(
        extractAdminApiError(
          error,
          "We could not preview your questions right now. Please check your formatting and try again.",
        ).message,
      );
    } finally {
      setIsParsing(false);
    }
  };

  const applyParsedBlocks = (
    items: ParsedQuestion[],
    mode: "append" | "replace",
    includeInvalidNote: boolean,
  ) => {
    const editable = items.map(fromParsedQuestion);
    onApplyQuestions(editable, mode);
    setAppliedBanner(
      `${mode === "replace" ? "Replaced question list with" : "Added"} ${editable.length} question${editable.length === 1 ? "" : "s"} below.${includeInvalidNote ? " Select a correct answer for any highlighted questions before saving." : " Review and click Save Questions when ready."}`,
    );
  };

  const handleReplaceValidClick = () => {
    if (!parseResult || parseResult.valid_questions.length === 0) {
      return;
    }
    if (existingQuestionCount > 0) {
      setConfirmReplaceMode("valid");
      return;
    }
    applyParsedBlocks(parseResult.valid_questions, "replace", false);
  };

  const handleImportAllWithFixes = () => {
    if (!parseResult || orderedBlocks.length === 0) {
      return;
    }
    if (existingQuestionCount > 0) {
      setConfirmReplaceMode("all");
      return;
    }
    applyParsedBlocks(
      orderedBlocks,
      "replace",
      parseResult.invalid_questions.length > 0,
    );
  };

  const handleConfirmReplace = () => {
    if (!parseResult || !confirmReplaceMode) {
      return;
    }
    if (confirmReplaceMode === "valid") {
      applyParsedBlocks(parseResult.valid_questions, "replace", false);
    } else {
      applyParsedBlocks(
        orderedBlocks,
        "replace",
        parseResult.invalid_questions.length > 0,
      );
    }
    setConfirmReplaceMode(null);
  };

  return (
    <Card as="section" aria-labelledby={`${baseId}-heading`}>
      <CardHeader>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div>
            <CardTitle as="h2" id={`${baseId}-heading`}>
              Import Questions and Answers
            </CardTitle>
            <CardDescription>
              Paste or upload questions and a separate answer key. Preview validates every answer
              before it can be saved as the exam's marking key.
            </CardDescription>
          </div>
          <Badge variant="outline">
            <ClipboardPaste className="size-3.5" aria-hidden="true" />
            <span>Preview only</span>
          </Badge>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        <div role="tablist" aria-label="Import content" className="flex gap-2 border-b border-border pb-3" onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          const next = activeInput === "questions" ? "answers" : "questions";
          setActiveInput(next);
          const tabs = event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]');
          tabs[next === "questions" ? 0 : 1]?.focus();
        }}>
          <Button id={`${baseId}-questions-tab`} type="button" role="tab" tabIndex={activeInput === "questions" ? 0 : -1} aria-selected={activeInput === "questions"} aria-controls={`${baseId}-questions-panel`} variant={activeInput === "questions" ? "default" : "outline"} onClick={() => setActiveInput("questions")}>Questions</Button>
          <Button id={`${baseId}-answers-tab`} type="button" role="tab" tabIndex={activeInput === "answers" ? 0 : -1} aria-selected={activeInput === "answers"} aria-controls={`${baseId}-answers-panel`} variant={activeInput === "answers" ? "default" : "outline"} onClick={() => setActiveInput("answers")}>Answer key</Button>
        </div>
        <div id={`${baseId}-questions-panel`} role="tabpanel" aria-labelledby={`${baseId}-questions-tab`} hidden={activeInput !== "questions"} className="space-y-5">
        <div className="rounded-lg border border-border bg-muted/40 p-3.5 text-xs leading-relaxed text-muted-foreground">
          <p className="font-semibold text-foreground">Formatting guide</p>
          <pre className="mt-1.5 overflow-x-auto whitespace-pre-wrap font-mono text-xs text-foreground">
            {`1. Question text...\nA. Option A\nB. Option B\nC. Option C (optional)\nD. Option D (optional)\nANSWER: B`}
          </pre>
          <p id={helpId} className="mt-2">
            Also accepts <code>1)</code>, <code>Q1:</code>, lowercase <code>a.</code>/<code>a)</code>,
            and <code>Ans: X</code> or <code>Correct Answer: X</code>. Each question needs 2–4
            options starting at <code>A</code>. Use an inline answer or the separate Answer key tab.
          </p>
        </div>

        <div className="field-group space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor={textareaId}>Paste questions</Label>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={disabled || isParsing || isReadingFile}
                onClick={() => {
                  setRawText(SAMPLE_FORMAT_TEXT);
                  setParseResult(null);
                  setRequestError(null);
                  setAppliedBanner(null);
                }}
              >
                <Sparkles className="size-4" aria-hidden="true" />
                <span>Load example</span>
              </Button>
              {rawText ? (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={disabled || isParsing || isReadingFile}
                  onClick={() => {
                    setRawText("");
                    setParseResult(null);
                    setRequestError(null);
                    setAppliedBanner(null);
                  }}
                >
                  Clear text
                </Button>
              ) : null}
            </div>
          </div>

          <Textarea
            id={textareaId}
            value={rawText}
            disabled={disabled || isParsing || isReadingFile}
            aria-describedby={helpId}
            rows={10}
            className="min-h-56 font-mono text-sm"
            placeholder={SAMPLE_FORMAT_TEXT}
            onChange={(event) => {
              setRawText(event.target.value);
              setParseResult(null);
              setRequestError(null);
              setAppliedBanner(null);
            }}
          />
        </div>

        <div
          className={cn("rounded-lg border-2 border-dashed border-border p-4 text-center", isDraggingFile && "border-primary bg-accent")}
          onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDraggingFile(true); }}
          onDragLeave={() => setIsDraggingFile(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDraggingFile(false);
            void loadTextFile(event.dataTransfer.files[0], "questions");
          }}
        >
          <Label htmlFor={`${baseId}-file`} className="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border px-4 text-sm font-medium focus-within:outline-2 focus-within:outline-primary">
            Choose question file
            <input
              id={`${baseId}-file`}
              type="file"
              accept=".txt,.md,text/plain,text/markdown"
              disabled={disabled || isParsing || isReadingFile}
              className="sr-only"
              onChange={(event) => {
                void loadTextFile(event.target.files?.[0], "questions");
                event.target.value = "";
              }}
            />
          </Label>
          <p className="mt-2 text-xs text-muted-foreground">Or drag and drop a .txt or .md file here (up to 100 MB). Preview and save the questions before publishing.</p>
        </div>
        </div>

        <div id={`${baseId}-answers-panel`} role="tabpanel" aria-labelledby={`${baseId}-answers-tab`} hidden={activeInput !== "answers"} className="space-y-5">
          <div className="rounded-lg border border-border bg-muted/40 p-3.5 text-sm text-muted-foreground">
            Enter one answer per numbered question, for example <code>1. B</code> and <code>2. A</code>.
            Every question must have exactly one matching answer. Leave this empty when answers
            are already marked inside the question text.
          </div>
          <div className="space-y-2">
            <Label htmlFor={answerKeyId}>Answers used for marking</Label>
            <Textarea id={answerKeyId} value={answerKeyText} disabled={disabled || isParsing || isReadingFile} rows={10} className="min-h-56 font-mono text-sm" placeholder={"1. B\n2. A\n3. D"} onChange={(event) => {
              setAnswerKeyText(event.target.value);
              setParseResult(null);
              setAppliedBanner(null);
              setRequestError(null);
            }} />
          </div>
          <div className={cn("rounded-lg border-2 border-dashed border-border p-4 text-center", isDraggingFile && "border-primary bg-accent")} onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDraggingFile(true); }} onDragLeave={() => setIsDraggingFile(false)} onDrop={(event) => {
            event.preventDefault();
            setIsDraggingFile(false);
            void loadTextFile(event.dataTransfer.files[0], "answers");
          }}>
            <Label htmlFor={`${baseId}-answer-file`} className="inline-flex min-h-11 cursor-pointer items-center rounded-md border border-border px-4 text-sm font-medium focus-within:outline-2 focus-within:outline-primary">
              Choose answer file
              <input id={`${baseId}-answer-file`} type="file" accept=".txt,.md,text/plain,text/markdown" disabled={disabled || isParsing || isReadingFile} className="sr-only" onChange={(event) => {
                void loadTextFile(event.target.files?.[0], "answers");
                event.target.value = "";
              }} />
            </Label>
            <p className="mt-2 text-xs text-muted-foreground">Or drag and drop a .txt or .md answer key (up to 100 MB).</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <Button
            type="button"
            disabled={disabled || isParsing || isReadingFile}
            onClick={() => void handleParse()}
          >
            <ListChecks className="size-4" aria-hidden="true" />
            <span>{isReadingFile ? "Reading file..." : isParsing ? "Previewing..." : "Preview Questions"}</span>
          </Button>
          {disabled ? (
            <span className="text-xs text-muted-foreground">
              Adding pasted questions is only available while this examination is a Draft.
            </span>
          ) : null}
        </div>

        {requestError ? (
          <Alert variant="destructive" role="alert">
            <AlertTitle>Could not preview questions</AlertTitle>
            <AlertDescription>{requestError}</AlertDescription>
          </Alert>
        ) : null}

        {appliedBanner ? (
          <Alert variant="success" role="status">
            <div className="flex items-start gap-2.5">
              <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
              <div>
                <AlertTitle>Questions added below</AlertTitle>
                <AlertDescription>{appliedBanner}</AlertDescription>
              </div>
            </div>
          </Alert>
        ) : null}

        {parseResult ? (
          <div className="space-y-4 border-t border-border pt-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-base font-semibold text-foreground">Question Preview</h3>
              <div className="flex flex-wrap gap-2" role="status">
                <Badge variant="secondary">Found: {parseResult.total_blocks}</Badge>
                <Badge variant={parseResult.valid_count > 0 ? "success" : "secondary"}>
                  Ready: {parseResult.valid_count}
                </Badge>
                <Badge variant={parseResult.error_count > 0 ? "destructive" : "secondary"}>
                  Needs attention: {parseResult.error_count}
                </Badge>
              </div>
            </div>

            {parseResult.errors.length > 0 ? (
              <Alert variant="destructive" role="alert">
                <div className="flex items-start gap-2.5">
                  <AlertTriangle className="mt-0.5 size-5 shrink-0" aria-hidden="true" />
                  <div className="min-w-0 space-y-2">
                    <AlertTitle>
                      {parseResult.error_count} issue
                      {parseResult.error_count === 1 ? "" : "s"} need attention
                    </AlertTitle>
                    <AlertDescription>
                      <p className="mb-2">
                        Fix the questions or answer key and preview again. Questions needing
                        fixes can also be edited below before saving.
                      </p>
                      <ul className="list-disc space-y-1 pl-5 break-words">
                        {parseResult.errors.map((err, index) => (
                          <li key={`${err.block_index}-${index}`}>
                            <strong>
                              {err.block_index === 0
                                ? "Answer key / formatting"
                                : `Question #${err.block_index}`}
                              :
                            </strong>{" "}
                            {err.message}
                          </li>
                        ))}
                      </ul>
                    </AlertDescription>
                  </div>
                </div>
              </Alert>
            ) : (
              <Alert variant="success" role="status">
                <div className="flex items-start gap-2.5">
                  <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                  <div>
                    <AlertTitle>
                      {parseResult.valid_count} question
                      {parseResult.valid_count === 1 ? "" : "s"} ready to add
                    </AlertTitle>
                    <AlertDescription>
                      Review the preview below, then add these questions to your exam or replace
                      your current list.
                    </AlertDescription>
                  </div>
                </div>
              </Alert>
            )}

            {orderedBlocks.length > 0 ? (
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2.5">
                  {parseResult.valid_questions.length > 0 ? (
                    <>
                      <Button
                        type="button"
                        disabled={disabled}
                        onClick={() =>
                          applyParsedBlocks(parseResult.valid_questions, "append", false)
                        }
                      >
                        <FilePlus2 className="size-4" aria-hidden="true" />
                        <span>Add ready questions ({parseResult.valid_questions.length})</span>
                      </Button>

                      <Button
                        type="button"
                        variant="outline"
                        disabled={disabled}
                        onClick={handleReplaceValidClick}
                      >
                        <Replace className="size-4" aria-hidden="true" />
                        <span>
                          Replace list with ready questions ({parseResult.valid_questions.length})
                        </span>
                      </Button>
                    </>
                  ) : null}

                  {parseResult.invalid_questions.length > 0 ? (
                    <Button
                      type="button"
                      variant="outline"
                      disabled={disabled}
                      onClick={() =>
                        applyParsedBlocks(
                          parseResult.invalid_questions,
                          "append",
                          true,
                        )
                      }
                    >
                      <Wrench className="size-4" aria-hidden="true" />
                      <span>
                        Add questions needing fixes ({parseResult.invalid_questions.length})
                      </span>
                    </Button>
                  ) : null}

                  {parseResult.invalid_questions.length > 0 &&
                  parseResult.valid_questions.length > 0 ? (
                    <Button
                      type="button"
                      variant="ghost"
                      disabled={disabled}
                      onClick={handleImportAllWithFixes}
                    >
                      <span>Replace list with all ({orderedBlocks.length}) to edit</span>
                    </Button>
                  ) : null}
                </div>

                <ol className="grid gap-3">
                  {orderedBlocks.map((block) => {
                    const missingAnswer = block.answer_label === null;
                    return (
                      <li
                        key={`preview-block-${block.position}`}
                        className={cn(
                          "rounded-lg border p-4",
                          block.valid
                            ? "border-border bg-card"
                            : "border-destructive-border bg-destructive-subtle/40",
                        )}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Question #{block.position}
                          </span>
                          <div className="flex flex-wrap gap-1.5">
                            {block.valid ? (
                              <Badge variant="success">
                                <CheckCircle2 className="size-3.5" aria-hidden="true" />
                                <span>Ready · Answer {block.answer_label}</span>
                              </Badge>
                            ) : (
                              <Badge variant="destructive">
                                <AlertTriangle className="size-3.5" aria-hidden="true" />
                                <span>
                                  {missingAnswer
                                    ? "Needs attention · Missing answer"
                                    : `Needs attention (${block.errors.length})`}
                                </span>
                              </Badge>
                            )}
                          </div>
                        </div>

                        <p className="mt-2 break-words text-sm font-medium text-foreground">
                          {block.question_text || (
                            <em className="text-destructive">(Missing question text)</em>
                          )}
                        </p>

                        {block.options.length > 0 ? (
                          <ul className="mt-2.5 grid gap-1.5 sm:grid-cols-2">
                            {block.options.map((opt) => {
                              const isAnswer = block.answer_label === opt.label;
                              return (
                                <li
                                  key={`${block.position}-${opt.label}`}
                                  className={cn(
                                    "min-w-0 break-words rounded-md border px-2.5 py-1.5 text-xs",
                                    isAnswer
                                      ? "border-success-border bg-success-subtle font-medium text-success"
                                      : "border-border bg-background text-foreground",
                                  )}
                                >
                                  <strong className="mr-1.5">{opt.label}.</strong>
                                  <span>{opt.option_text}</span>
                                </li>
                              );
                            })}
                          </ul>
                        ) : null}

                        {block.errors.length > 0 ? (
                          <ul className="mt-3 list-disc space-y-0.5 pl-5 break-words text-xs font-medium text-destructive">
                            {block.errors.map((msg, errIdx) => (
                              <li key={errIdx}>{msg}</li>
                            ))}
                          </ul>
                        ) : null}
                      </li>
                    );
                  })}
                </ol>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>

      <CardFooter className="text-xs text-muted-foreground">
        Previewing does not save changes yet — click Save Questions below when you are ready.
      </CardFooter>

      <ConfirmDialog
        open={confirmReplaceMode !== null}
        onOpenChange={(open) => {
          if (!open) {
            setConfirmReplaceMode(null);
          }
        }}
        title="Replace current questions?"
        description={`This will replace the ${existingQuestionCount} question${existingQuestionCount === 1 ? "" : "s"} currently in your editor. Nothing is saved until you click Save Questions.`}
        confirmLabel="Replace questions"
        confirmVariant="destructive"
        onConfirm={handleConfirmReplace}
      />
    </Card>
  );
}
