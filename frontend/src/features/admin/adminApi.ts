import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
  apiPut,
  type ApiRequestOptions,
} from "@/lib/api";
import type {
  AttemptResultOut,
  ExamAdminOut,
  ExamAdminResultsResponse,
  ExamCreate,
  ExamStatus,
  ExamUpdate,
  ExamWithQuestionsAdmin,
  ParseQuestionsResponse,
  QuestionAdminOut,
  QuestionCreate,
} from "@/types/adminExam";

export function listAdminExams(
  status?: ExamStatus,
  options?: ApiRequestOptions,
): Promise<ExamAdminOut[]> {
  const query = status ? `?status=${encodeURIComponent(status)}` : "";
  return apiGet<ExamAdminOut[]>(`/api/admin/exams${query}`, options);
}

export function createAdminExam(
  payload: ExamCreate,
  options?: ApiRequestOptions,
): Promise<ExamAdminOut> {
  return apiPost<ExamAdminOut>("/api/admin/exams", {
    ...options,
    body: payload,
  });
}

export function getAdminExam(
  examId: string,
  options?: ApiRequestOptions,
): Promise<ExamWithQuestionsAdmin> {
  return apiGet<ExamWithQuestionsAdmin>(
    `/api/admin/exams/${encodeURIComponent(examId)}`,
    options,
  );
}

export function updateAdminExam(
  examId: string,
  payload: ExamUpdate,
  options?: ApiRequestOptions,
): Promise<ExamAdminOut> {
  return apiPatch<ExamAdminOut>(
    `/api/admin/exams/${encodeURIComponent(examId)}`,
    {
      ...options,
      body: payload,
    },
  );
}

export function deleteAdminExam(
  examId: string,
  options?: ApiRequestOptions,
): Promise<void> {
  return apiDelete<void>(`/api/admin/exams/${encodeURIComponent(examId)}`, options);
}

export function parseQuestions(
  rawText: string,
  answerKeyText?: string,
  options?: ApiRequestOptions,
): Promise<ParseQuestionsResponse> {
  return apiPost<ParseQuestionsResponse>("/api/admin/exams/parse-questions", {
    timeoutMs: 120000,
    ...options,
    body: { raw_text: rawText, answer_key_text: answerKeyText || null },
  });
}

export function importQuestionPdf(
  examId: string,
  file: File,
  answerKeyText: string,
): Promise<ParseQuestionsResponse> {
  const body = new FormData();
  body.set("file", file);
  body.set("answer_key_text", answerKeyText);
  return apiPost<ParseQuestionsResponse>(
    `/api/admin/exams/${encodeURIComponent(examId)}/import-pdf`,
    { body, timeoutMs: 120000 },
  );
}

export function updateQuestionCrops(
  examId: string,
  sourceId: string,
  questionNumber: number,
  regions: Array<{ page: number; bbox: number[] }>,
  dpi = 200,
  padding = 0,
): Promise<{ regions: Array<{ page: number; bbox: number[] }>; image_urls: string[] }> {
  return apiPut(
    `/api/admin/exams/${encodeURIComponent(examId)}/sources/${encodeURIComponent(sourceId)}/questions/${questionNumber}/crops`,
    { body: { regions, dpi, padding }, timeoutMs: 120000 },
  );
}

export function saveExamQuestions(
  examId: string,
  questions: QuestionCreate[],
  options?: ApiRequestOptions,
): Promise<ExamWithQuestionsAdmin> {
  return apiPut<ExamWithQuestionsAdmin>(
    `/api/admin/exams/${encodeURIComponent(examId)}/questions`,
    {
      timeoutMs: 20000,
      ...options,
      body: { questions },
    },
  );
}

export function addExamQuestion(
  examId: string,
  payload: QuestionCreate,
  options?: ApiRequestOptions,
): Promise<QuestionAdminOut> {
  return apiPost<QuestionAdminOut>(
    `/api/admin/exams/${encodeURIComponent(examId)}/questions`,
    {
      ...options,
      body: payload,
    },
  );
}

export function updateExamQuestion(
  examId: string,
  questionId: string,
  payload: QuestionCreate,
  options?: ApiRequestOptions,
): Promise<QuestionAdminOut> {
  return apiPut<QuestionAdminOut>(
    `/api/admin/exams/${encodeURIComponent(examId)}/questions/${encodeURIComponent(questionId)}`,
    {
      ...options,
      body: payload,
    },
  );
}

export function deleteExamQuestion(
  examId: string,
  questionId: string,
  options?: ApiRequestOptions,
): Promise<void> {
  return apiDelete<void>(
    `/api/admin/exams/${encodeURIComponent(examId)}/questions/${encodeURIComponent(questionId)}`,
    options,
  );
}

export function publishAdminExam(
  examId: string,
  options?: ApiRequestOptions,
): Promise<ExamAdminOut> {
  return apiPost<ExamAdminOut>(
    `/api/admin/exams/${encodeURIComponent(examId)}/publish`,
    options,
  );
}

export function closeAdminExam(
  examId: string,
  options?: ApiRequestOptions,
): Promise<ExamAdminOut> {
  return apiPost<ExamAdminOut>(
    `/api/admin/exams/${encodeURIComponent(examId)}/close`,
    options,
  );
}

export function getAdminExamResults(
  examId: string,
  options?: ApiRequestOptions,
): Promise<ExamAdminResultsResponse> {
  return apiGet<ExamAdminResultsResponse>(
    `/api/admin/exams/${encodeURIComponent(examId)}/results`,
    options,
  );
}

export function getAdminAttemptDetail(
  attemptId: string,
  options?: ApiRequestOptions,
): Promise<AttemptResultOut> {
  return apiGet<AttemptResultOut>(
    `/api/admin/attempts/${encodeURIComponent(attemptId)}`,
    options,
  );
}
