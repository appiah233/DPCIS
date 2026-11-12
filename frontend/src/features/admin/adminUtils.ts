import { ApiClientError } from "@/lib/api";
import type {
  DecimalValue,
  OptionLabel,
  ParsedQuestion,
  QuestionAdminOut,
  QuestionCreate,
  QuestionOptionCreate,
} from "@/types/adminExam";

export const OPTION_LABELS: readonly OptionLabel[] = ["A", "B", "C", "D"];

export interface EditableOption {
  label: OptionLabel;
  option_text: string;
  is_correct: boolean;
}

export interface EditableQuestion {
  localKey: string;
  question_text: string;
  points: string;
  options: EditableOption[];
  parserErrors?: string[];
}

export interface QuestionValidationIssue {
  questionErrors: string[];
  optionErrors: Record<number, string>;
}

export interface ExtractedAdminApiError {
  message: string;
  validationErrors: string[];
}

let localKeyCounter = 0;

export function createLocalQuestionKey(): string {
  localKeyCounter += 1;
  return `q-${Date.now()}-${localKeyCounter}`;
}

export function extractAdminApiError(
  error: unknown,
  fallbackMessage = "Something went wrong. Please try again.",
): ExtractedAdminApiError {
  if (error instanceof ApiClientError) {
    const validationErrors: string[] = [];
    if (error.detail && typeof error.detail === "object" && "errors" in error.detail) {
      const rawErrors = (error.detail as { errors?: unknown }).errors;
      if (Array.isArray(rawErrors)) {
        for (const item of rawErrors) {
          if (typeof item === "string" && item.trim()) {
            validationErrors.push(item.trim());
          }
        }
      }
    }
    return {
      message: error.message || fallbackMessage,
      validationErrors,
    };
  }

  if (error instanceof Error && error.message.trim()) {
    return {
      message: error.message,
      validationErrors: [],
    };
  }

  return {
    message: fallbackMessage,
    validationErrors: [],
  };
}

export function formatDecimal(
  value: DecimalValue | null | undefined,
  suffix = "",
): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  const numeric = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(numeric)) {
    return String(value);
  }
  const formatted = Number.isInteger(numeric)
    ? String(numeric)
    : numeric.toFixed(2).replace(/\.?0+$/, "");
  return suffix ? `${formatted}${suffix}` : formatted;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  const timestamp = Date.parse(iso);
  if (!Number.isFinite(timestamp)) {
    return "—";
  }
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(timestamp));
}

export function formatSubmissionReason(reason: string | null | undefined): string {
  if (!reason) {
    return "—";
  }
  if (reason === "STUDENT_SUBMITTED") {
    return "Submitted manually";
  }
  if (reason === "TIMER_EXPIRED") {
    return "Timer expired";
  }
  return reason;
}

export function normalizeOptionTextForDupCheck(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

export function relabelSequentialOptions(options: EditableOption[]): EditableOption[] {
  return options.slice(0, OPTION_LABELS.length).map((option, index) => ({
    ...option,
    label: OPTION_LABELS[index],
  }));
}

export function createBlankEditableQuestion(): EditableQuestion {
  return {
    localKey: createLocalQuestionKey(),
    question_text: "",
    points: "1.00",
    options: [
      { label: "A", option_text: "", is_correct: true },
      { label: "B", option_text: "", is_correct: false },
      { label: "C", option_text: "", is_correct: false },
      { label: "D", option_text: "", is_correct: false },
    ],
  };
}

export function fromAdminQuestions(questions: QuestionAdminOut[]): EditableQuestion[] {
  const sorted = [...questions].sort((a, b) => a.position - b.position);
  return sorted.map((question) => {
    const sortedOptions = [...question.options].sort(
      (a, b) => a.position - b.position || a.label.localeCompare(b.label),
    );
    return {
      localKey: createLocalQuestionKey(),
      question_text: question.question_text,
      points: formatPointsForInput(question.points),
      options: relabelSequentialOptions(
        sortedOptions.map((option) => ({
          label: option.label,
          option_text: option.option_text,
          is_correct: Boolean(option.is_correct),
        })),
      ),
    };
  });
}

export function fromParsedQuestion(parsed: ParsedQuestion): EditableQuestion {
  const mappedOptions: EditableOption[] = parsed.options.map((opt) => ({
    label: opt.label,
    option_text: opt.option_text,
    is_correct: parsed.answer_label !== null && opt.label === parsed.answer_label,
  }));

  while (mappedOptions.length < 2) {
    mappedOptions.push({
      label: OPTION_LABELS[mappedOptions.length],
      option_text: "",
      is_correct: false,
    });
  }

  return {
    localKey: createLocalQuestionKey(),
    question_text: parsed.question_text,
    points: formatPointsForInput(parsed.points),
    options: relabelSequentialOptions(mappedOptions),
    parserErrors: parsed.errors.length > 0 ? [...parsed.errors] : undefined,
  };
}

function formatPointsForInput(value: DecimalValue): string {
  const numeric = typeof value === "number" ? value : Number.parseFloat(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return "1.00";
  }
  return numeric.toFixed(2);
}

export function validateEditableQuestion(
  question: EditableQuestion,
): QuestionValidationIssue {
  const questionErrors: string[] = [];
  const optionErrors: Record<number, string> = {};

  if (!question.question_text.trim()) {
    questionErrors.push("Question text is required.");
  }

  const parsedPoints = Number.parseFloat(question.points);
  if (
    !question.points.trim() ||
    !Number.isFinite(parsedPoints) ||
    parsedPoints <= 0 ||
    parsedPoints > 999.99
  ) {
    questionErrors.push("Points must be between 0.01 and 999.99.");
  } else if (!/^\d+(\.\d{1,2})?$/.test(question.points.trim())) {
    questionErrors.push("Points may have at most 2 decimal places.");
  }

  if (question.options.length < 2 || question.options.length > 4) {
    questionErrors.push("Each question must have between 2 and 4 options.");
  }

  const seenNormalizedTexts = new Map<string, OptionLabel>();
  let correctCount = 0;

  question.options.forEach((option, index) => {
    if (option.is_correct) {
      correctCount += 1;
    }

    const trimmed = option.option_text.trim();
    if (!trimmed) {
      optionErrors[index] = `Option ${option.label} cannot be empty.`;
      return;
    }

    const normalized = normalizeOptionTextForDupCheck(trimmed);
    const existingLabel = seenNormalizedTexts.get(normalized);
    if (existingLabel) {
      optionErrors[index] =
        `Option ${option.label} duplicates Option ${existingLabel}.`;
    } else {
      seenNormalizedTexts.set(normalized, option.label);
    }
  });

  if (Object.keys(optionErrors).length > 0) {
    questionErrors.push("Fix highlighted option issues before saving.");
  }

  if (correctCount !== 1) {
    questionErrors.push("Select exactly one correct answer (A–D).");
  }

  return {
    questionErrors,
    optionErrors,
  };
}

export function hasAnyQuestionValidationIssues(
  questions: EditableQuestion[],
): boolean {
  return questions.some((question) => {
    const issue = validateEditableQuestion(question);
    return (
      issue.questionErrors.length > 0 ||
      Object.keys(issue.optionErrors).length > 0
    );
  });
}

export function toQuestionCreates(questions: EditableQuestion[]): QuestionCreate[] {
  return questions.map((question, index) => {
    const relabeled = relabelSequentialOptions(question.options);
    const options: QuestionOptionCreate[] = relabeled.map((option) => ({
      label: option.label,
      option_text: option.option_text.trim(),
      is_correct: option.is_correct,
    }));

    return {
      question_text: question.question_text.trim(),
      position: index,
      points: Number.parseFloat(question.points).toFixed(2),
      options,
    };
  });
}

export function computeQuestionsSignature(questions: EditableQuestion[]): string {
  return JSON.stringify(
    questions.map((question) => ({
      question_text: question.question_text.trim(),
      points: question.points.trim(),
      options: relabelSequentialOptions(question.options).map((option) => ({
        label: option.label,
        option_text: option.option_text.trim(),
        is_correct: option.is_correct,
      })),
    })),
  );
}
