import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { AnswerSaveStatus } from "@/components/exam/ExamProgressHeader";
import { formatStudentErrorMessage } from "@/features/student/formatters";
import {
  fetchAttemptDelivery,
  saveAttemptAnswer,
  submitAttempt,
} from "@/features/student/studentApi";
import { ApiClientError } from "@/lib/api";
import type { AttemptDelivery, AttemptQuestionDelivery } from "@/types/studentExam";

export interface FailedSaveNotice {
  questionId: string;
  questionNumber: number;
  attemptedOptionId: string | null;
  attemptedLabel: string | null;
  message: string;
}

export interface AttemptRunnerState {
  status: "loading" | "ready" | "error";
  delivery: AttemptDelivery | null;
  loadError: string | null;
  currentIndex: number;
  setCurrentIndex: (index: number) => void;
  answers: Record<string, string | null>;
  saveStatus: AnswerSaveStatus;
  saveMessage: string | undefined;
  failedSave: FailedSaveNotice | null;
  dismissFailedSave: () => void;
  retryFailedSave: () => void;
  selectOption: (questionId: string, optionId: string | null) => void;
  isLocked: boolean;
  isSubmitting: boolean;
  isExpired: boolean;
  submitError: string | null;
  submitNow: (reason: "manual" | "expired") => Promise<void>;
  reload: () => void;
}

function getStorageKey(attemptId: string): string {
  return `dpcis_exam_q_${attemptId}`;
}

function readStoredQuestionIndex(attemptId: string, totalQuestions: number): number {
  if (totalQuestions <= 0) {
    return 0;
  }
  try {
    const raw = window.sessionStorage.getItem(getStorageKey(attemptId));
    if (!raw) {
      return 0;
    }
    const parsed = Number.parseInt(raw, 10);
    if (!Number.isFinite(parsed)) {
      return 0;
    }
    return Math.min(totalQuestions - 1, Math.max(0, parsed));
  } catch {
    return 0;
  }
}

function writeStoredQuestionIndex(attemptId: string, index: number): void {
  try {
    window.sessionStorage.setItem(getStorageKey(attemptId), String(index));
  } catch {
    // Ignore storage quota or private browsing errors.
  }
}

function clearStoredQuestionIndex(attemptId: string): void {
  try {
    window.sessionStorage.removeItem(getStorageKey(attemptId));
  } catch {
    // Ignore storage cleanup errors.
  }
}

function findQuestionMeta(
  questions: readonly AttemptQuestionDelivery[] | undefined,
  questionId: string,
  optionId: string | null,
): { questionNumber: number; optionLabel: string | null } {
  if (!questions) {
    return { questionNumber: 1, optionLabel: null };
  }
  const index = questions.findIndex((q) => q.id === questionId);
  const question = index >= 0 ? questions[index] : undefined;
  const optionLabel =
    question && optionId
      ? (question.options.find((opt) => opt.id === optionId)?.label ?? null)
      : null;
  return {
    questionNumber: index >= 0 ? index + 1 : 1,
    optionLabel,
  };
}

function isAttemptFinalizedConflict(error: unknown): error is ApiClientError {
  return (
    error instanceof ApiClientError &&
    error.status === 409 &&
    (!error.code ||
      error.code === "ATTEMPT_EXPIRED" ||
      error.code === "ATTEMPT_ALREADY_GRADED")
  );
}

function getAttemptConflictNotice(error: ApiClientError): string {
  const fallback =
    error.code === "ATTEMPT_EXPIRED"
      ? "Examination time has expired. Your attempt has been finalized."
      : "This examination attempt has already been finalized.";
  return formatStudentErrorMessage(error, fallback);
}

export function useAttemptRunner(attemptId: string | undefined): AttemptRunnerState {
  const navigate = useNavigate();

  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [delivery, setDelivery] = useState<AttemptDelivery | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [currentIndex, setCurrentIndexState] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string | null>>({});
  const [saveStatus, setSaveStatus] = useState<AnswerSaveStatus>("idle");
  const [saveMessage, setSaveMessage] = useState<string | undefined>(undefined);
  const [failedSave, setFailedSave] = useState<FailedSaveNotice | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isExpired, setIsExpired] = useState(false);
  const [isFinalized, setIsFinalized] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  const deliveryRef = useRef<AttemptDelivery | null>(null);
  const committedAnswersRef = useRef<Record<string, string | null>>({});
  const desiredOptionRef = useRef<Map<string, string | null>>(new Map());
  const activeSaveLoopsRef = useRef<Map<string, Promise<void>>>(new Map());
  const failedSaveRef = useRef<FailedSaveNotice | null>(null);
  const submitInFlightRef = useRef(false);
  const isMountedRef = useRef(true);

  useEffect(() => {
    deliveryRef.current = delivery;
  }, [delivery]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const redirectToResult = useCallback(
    (notice?: string) => {
      if (!attemptId) {
        return;
      }
      clearStoredQuestionIndex(attemptId);
      setIsFinalized(true);
      navigate(`/student/results/${encodeURIComponent(attemptId)}`, {
        replace: true,
        state: notice ? { notice } : undefined,
      });
    },
    [attemptId, navigate],
  );

  const syncAggregateSaveStatus = useCallback((overrideError?: string) => {
    if (!isMountedRef.current) {
      return;
    }
    if (activeSaveLoopsRef.current.size > 0) {
      setSaveStatus("saving");
      setSaveMessage("Saving...");
      return;
    }
    if (overrideError || failedSaveRef.current !== null) {
      setSaveStatus("error");
      setSaveMessage("Save failed");
      return;
    }
    setSaveStatus("saved");
    setSaveMessage("All changes saved");
  }, []);

  const submitNow = useCallback(
    async (reason: "manual" | "expired") => {
      if (!attemptId || submitInFlightRef.current) {
        return;
      }

      submitInFlightRef.current = true;
      setIsSubmitting(true);
      setSubmitError(null);
      if (reason === "expired") {
        setIsExpired(true);
      }

      try {
        if (activeSaveLoopsRef.current.size > 0) {
          await Promise.allSettled(Array.from(activeSaveLoopsRef.current.values()));
        }

        await submitAttempt(attemptId);
        if (!isMountedRef.current) {
          return;
        }
        redirectToResult(
          reason === "expired"
            ? "Time expired. Your examination was automatically submitted."
            : undefined,
        );
      } catch (error) {
        if (!isMountedRef.current) {
          return;
        }
        if (isAttemptFinalizedConflict(error)) {
          redirectToResult(getAttemptConflictNotice(error));
          return;
        }
        setSubmitError(
          formatStudentErrorMessage(
            error,
            "Unable to submit your examination right now. Please try again.",
          ),
        );
        submitInFlightRef.current = false;
        setIsSubmitting(false);
      }
    },
    [attemptId, redirectToResult],
  );

  useEffect(() => {
    if (!attemptId) {
      setStatus("error");
      setLoadError("No attempt identifier was provided.");
      return;
    }

    const controller = new AbortController();
    desiredOptionRef.current.clear();
    activeSaveLoopsRef.current.clear();
    committedAnswersRef.current = {};
    failedSaveRef.current = null;
    submitInFlightRef.current = false;

    setStatus("loading");
    setLoadError(null);
    setFailedSave(null);
    setSubmitError(null);
    setSaveStatus("idle");
    setSaveMessage(undefined);
    setIsExpired(false);
    setIsFinalized(false);
    setIsSubmitting(false);

    fetchAttemptDelivery(attemptId, { signal: controller.signal })
      .then((loaded) => {
        if (controller.signal.aborted || !isMountedRef.current) {
          return;
        }
        const initialAnswers: Record<string, string | null> = { ...loaded.saved_answers };
        committedAnswersRef.current = { ...loaded.saved_answers };
        deliveryRef.current = loaded;

        setDelivery(loaded);
        setAnswers(initialAnswers);
        setCurrentIndexState(readStoredQuestionIndex(attemptId, loaded.questions.length));
        setStatus("ready");

        if (Object.values(initialAnswers).some((val) => val !== null && val !== undefined)) {
          setSaveStatus("saved");
          setSaveMessage("Saved answers restored");
        }

        const expiresMs = Date.parse(loaded.expires_at);
        const serverNowMs = Date.parse(loaded.server_now);
        if (Number.isFinite(expiresMs) && Number.isFinite(serverNowMs) && expiresMs <= serverNowMs) {
          void submitNow("expired");
        }
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted || !isMountedRef.current) {
          return;
        }
        if (isAttemptFinalizedConflict(error)) {
          redirectToResult(getAttemptConflictNotice(error));
          return;
        }
        setStatus("error");
        setLoadError(
          formatStudentErrorMessage(
            error,
            "Unable to load your examination session.",
          ),
        );
      });

    return () => {
      controller.abort();
    };
  }, [attemptId, reloadNonce, redirectToResult, submitNow]);

  const setCurrentIndex = useCallback(
    (nextIndex: number) => {
      const total = deliveryRef.current?.questions.length ?? 0;
      const clamped = total > 0 ? Math.min(total - 1, Math.max(0, nextIndex)) : 0;
      setCurrentIndexState(clamped);
      if (attemptId) {
        writeStoredQuestionIndex(attemptId, clamped);
      }
    },
    [attemptId],
  );

  const runSaveLoop = useCallback(
    async (questionId: string) => {
      if (!attemptId) {
        return;
      }

      try {
        while (desiredOptionRef.current.has(questionId)) {
          const targetOptionId = desiredOptionRef.current.get(questionId) ?? null;
          const committedOptionId = committedAnswersRef.current[questionId] ?? null;

          if (targetOptionId === committedOptionId) {
            desiredOptionRef.current.delete(questionId);
            continue;
          }

          const saved = await saveAttemptAnswer(attemptId, questionId, targetOptionId);
          if (!isMountedRef.current) {
            return;
          }

          committedAnswersRef.current[questionId] = saved.selected_option_id;

          if (desiredOptionRef.current.get(questionId) === targetOptionId) {
            desiredOptionRef.current.delete(questionId);
          }
        }
      } catch (error) {
        const failedTarget = desiredOptionRef.current.get(questionId) ?? null;
        desiredOptionRef.current.delete(questionId);

        if (!isMountedRef.current) {
          return;
        }

        if (isAttemptFinalizedConflict(error)) {
          setIsFinalized(true);
          redirectToResult(getAttemptConflictNotice(error));
          return;
        }

        const fallbackOptionId = committedAnswersRef.current[questionId] ?? null;
        setAnswers((prev) => ({
          ...prev,
          [questionId]: fallbackOptionId,
        }));

        const meta = findQuestionMeta(
          deliveryRef.current?.questions,
          questionId,
          failedTarget,
        );
        const message = formatStudentErrorMessage(
          error,
          "Could not save your answer selection.",
        );

        const nextFailedSave: FailedSaveNotice = {
          questionId,
          questionNumber: meta.questionNumber,
          attemptedOptionId: failedTarget,
          attemptedLabel: meta.optionLabel,
          message,
        };
        failedSaveRef.current = nextFailedSave;
        setFailedSave(nextFailedSave);
        activeSaveLoopsRef.current.delete(questionId);
        syncAggregateSaveStatus(message);
        return;
      }

      activeSaveLoopsRef.current.delete(questionId);
      syncAggregateSaveStatus();
    },
    [attemptId, redirectToResult, syncAggregateSaveStatus],
  );

  const selectOption = useCallback(
    (questionId: string, optionId: string | null) => {
      if (!attemptId || isSubmitting || isExpired || isFinalized) {
        return;
      }

      setAnswers((prev) => ({
        ...prev,
        [questionId]: optionId,
      }));
      if (failedSaveRef.current?.questionId === questionId) {
        failedSaveRef.current = null;
      }
      setFailedSave((prev) => (prev?.questionId === questionId ? null : prev));
      desiredOptionRef.current.set(questionId, optionId);

      if (!activeSaveLoopsRef.current.has(questionId)) {
        const loopPromise = runSaveLoop(questionId);
        activeSaveLoopsRef.current.set(questionId, loopPromise);
      }
      syncAggregateSaveStatus();
    },
    [attemptId, isExpired, isFinalized, isSubmitting, runSaveLoop, syncAggregateSaveStatus],
  );

  const dismissFailedSave = useCallback(() => {
    failedSaveRef.current = null;
    setFailedSave(null);
    if (activeSaveLoopsRef.current.size === 0 && saveStatus === "error") {
      setSaveStatus("idle");
      setSaveMessage(undefined);
    }
  }, [saveStatus]);

  const retryFailedSave = useCallback(() => {
    if (!failedSave) {
      return;
    }
    const { questionId, attemptedOptionId } = failedSave;
    failedSaveRef.current = null;
    setFailedSave(null);
    selectOption(questionId, attemptedOptionId);
  }, [failedSave, selectOption]);

  const reload = useCallback(() => {
    setReloadNonce((n) => n + 1);
  }, []);

  return {
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
    isLocked: isSubmitting || isExpired || isFinalized,
    isSubmitting,
    isExpired,
    submitError,
    submitNow,
    reload,
  };
}
