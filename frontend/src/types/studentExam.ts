export type OptionLabel = "A" | "B" | "C" | "D";

export type SubmissionReason = "STUDENT_SUBMITTED" | "TIMER_EXPIRED" | string;

export interface ExamStudentOut {
  id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  duration_minutes: number;
  pass_mark: string | number;
  question_limit: number | null;
  randomize_questions: boolean;
  randomize_options: boolean;
  max_attempts: number;
  show_result: boolean;
  question_count: number;
  attempts_used: number;
  active_attempt_id: string | null;
  can_start: boolean;
  published_at: string | null;
}

export interface AttemptStartResponse {
  attempt_id: string;
  exam_id: string;
  status: string;
  started_at: string;
  expires_at: string;
  server_now: string;
  total_questions: number;
  duration_minutes: number;
  resumed: boolean;
}

/**
 * Student-facing option delivered during an active attempt.
 * Intentionally excludes any answer-key metadata (`is_correct`).
 */
export interface AttemptOptionDelivery {
  id: string;
  label: OptionLabel;
  option_text: string;
}

export interface AttemptQuestionDelivery {
  id: string;
  display_order: number;
  question_text: string;
  points: string | number;
  options: AttemptOptionDelivery[];
}

export interface AttemptDelivery {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  duration_minutes: number;
  status: string;
  started_at: string;
  expires_at: string;
  server_now: string;
  total_questions: number;
  questions: AttemptQuestionDelivery[];
  saved_answers: Record<string, string | null>;
}

export interface AnswerSaveRequest {
  selected_option_id: string | null;
}

export interface AnswerSaveResponse {
  attempt_id: string;
  question_id: string;
  selected_option_id: string | null;
  answered_at: string;
  updated_at: string;
}

export interface AttemptQuestionReviewOption {
  id: string;
  label: OptionLabel;
  option_text: string;
  is_correct: boolean;
}

export interface AttemptQuestionReviewItem {
  question_id: string;
  display_order: number;
  question_text: string;
  selected_option_id: string | null;
  correct_option_id: string | null;
  is_correct: boolean;
  points_earned: string | number;
  points_available: string | number;
  options: AttemptQuestionReviewOption[];
}

export interface AttemptResultOut {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  status: string;
  submission_reason: SubmissionReason | null;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered_questions: number;
  points_earned: string | number;
  points_available: string | number;
  percentage: string | number;
  pass_mark: string | number;
  passed: boolean;
  result_visible: true;
  show_correct_answers: boolean;
  question_review: AttemptQuestionReviewItem[] | null;
}

export interface AttemptSubmittedHiddenOut {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  status: string;
  submission_reason: SubmissionReason | null;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  total_questions: number;
  result_visible: false;
  show_correct_answers: false;
  message: string;
}

export type AttemptResultResponse = AttemptResultOut | AttemptSubmittedHiddenOut;

export interface StudentAttemptSummary {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  status: string;
  submission_reason: SubmissionReason | null;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  total_questions: number;
  result_visible: boolean;
  points_earned: string | number | null;
  points_available: string | number | null;
  percentage: string | number | null;
  passed: boolean | null;
}
