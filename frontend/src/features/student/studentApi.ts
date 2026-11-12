import { apiGet, apiPost, apiPut, type ApiRequestOptions } from "@/lib/api";
import type {
  AnswerSaveRequest,
  AnswerSaveResponse,
  AttemptDelivery,
  AttemptResultResponse,
  AttemptStartResponse,
  ExamStudentOut,
  StudentAttemptSummary,
} from "@/types/studentExam";

export function listAvailableExams(options?: ApiRequestOptions): Promise<ExamStudentOut[]> {
  return apiGet<ExamStudentOut[]>("/api/exams", options);
}

export function getStudentExamDetail(
  examId: string,
  options?: ApiRequestOptions,
): Promise<ExamStudentOut> {
  return apiGet<ExamStudentOut>(`/api/exams/${encodeURIComponent(examId)}`, options);
}

export function startOrResumeAttempt(
  examId: string,
  options?: ApiRequestOptions,
): Promise<AttemptStartResponse> {
  return apiPost<AttemptStartResponse>(
    `/api/exams/${encodeURIComponent(examId)}/attempts`,
    {
      ...options,
      body: {},
    },
  );
}

export function fetchAttemptDelivery(
  attemptId: string,
  options?: ApiRequestOptions,
): Promise<AttemptDelivery> {
  return apiGet<AttemptDelivery>(`/api/attempts/${encodeURIComponent(attemptId)}`, options);
}

export function saveAttemptAnswer(
  attemptId: string,
  questionId: string,
  selectedOptionId: string | null,
  options?: ApiRequestOptions,
): Promise<AnswerSaveResponse> {
  const payload: AnswerSaveRequest = { selected_option_id: selectedOptionId };
  return apiPut<AnswerSaveResponse>(
    `/api/attempts/${encodeURIComponent(attemptId)}/answers/${encodeURIComponent(questionId)}`,
    {
      ...options,
      body: payload,
    },
  );
}

export function submitAttempt(
  attemptId: string,
  options?: ApiRequestOptions,
): Promise<AttemptResultResponse> {
  return apiPost<AttemptResultResponse>(
    `/api/attempts/${encodeURIComponent(attemptId)}/submit`,
    {
      timeoutMs: 15000,
      ...options,
      body: { confirm: true },
    },
  );
}

export function getAttemptResult(
  attemptId: string,
  options?: ApiRequestOptions,
): Promise<AttemptResultResponse> {
  return apiGet<AttemptResultResponse>(
    `/api/attempts/${encodeURIComponent(attemptId)}/result`,
    options,
  );
}

export function listStudentAttempts(
  options?: ApiRequestOptions,
): Promise<StudentAttemptSummary[]> {
  return apiGet<StudentAttemptSummary[]>("/api/student/attempts", options);
}
