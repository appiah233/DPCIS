export type OptionLabel = "A" | "B" | "C" | "D";

export type ExamStatus = "DRAFT" | "PUBLISHED" | "CLOSED";

export type DecimalValue = string | number;

export interface QuestionOptionCreate {
  label: OptionLabel;
  option_text: string;
  is_correct: boolean;
}

export interface QuestionOptionAdminOut {
  id: string | null;
  label: OptionLabel;
  option_text: string;
  is_correct: boolean;
  position: number;
}

export interface ExamCreate {
  title: string;
  description: string | null;
  instructions: string | null;
  duration_minutes: number;
  pass_mark: DecimalValue;
  question_limit: number | null;
  randomize_questions: boolean;
  randomize_options: boolean;
  max_attempts: number;
  show_result: boolean;
  show_correct_answers: boolean;
}

export type ExamUpdate = Partial<ExamCreate>;

export interface ExamAdminOut {
  id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  duration_minutes: number;
  pass_mark: DecimalValue;
  question_limit: number | null;
  randomize_questions: boolean;
  randomize_options: boolean;
  max_attempts: number;
  show_result: boolean;
  show_correct_answers: boolean;
  status: ExamStatus;
  created_by: string;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  closed_at: string | null;
  question_count: number;
}

export interface QuestionAdminOut {
  id: string;
  question_text: string;
  source_file_id?: string | null;
  source_number?: number | null;
  image_urls?: string[];
  image_regions?: Array<{ page: number; bbox: number[] }>;
  pdf_options_text?: Record<string, string>;
  pdf_warnings?: string[];
  pdf_confidence?: DecimalValue | null;
  position: number;
  points: DecimalValue;
  options: QuestionOptionAdminOut[];
}

export interface ExamWithQuestionsAdmin extends ExamAdminOut {
  questions: QuestionAdminOut[];
}

export interface QuestionCreate {
  question_text: string;
  source_file_id?: string | null;
  source_number?: number | null;
  pdf_options_text?: Record<string, string>;
  pdf_warnings?: string[];
  pdf_confidence?: DecimalValue | null;
  position?: number | null;
  points: DecimalValue;
  options: QuestionOptionCreate[];
}

export interface ParsedOption {
  label: OptionLabel;
  option_text: string;
}

export interface ParsedQuestion {
  question_text: string;
  source_file_id?: string | null;
  source_number?: number | null;
  image_urls?: string[];
  image_regions?: Array<{ page: number; bbox: number[] }>;
  warnings?: string[];
  pdf_options_text?: Record<string, string>;
  pdf_confidence?: DecimalValue | null;
  position: number;
  points: DecimalValue;
  options: ParsedOption[];
  answer_label: OptionLabel | null;
  valid: boolean;
  errors: string[];
}

export interface ParseQuestionsRequest {
  raw_text: string;
}

export interface ParseQuestionsError {
  block_index: number;
  message: string;
}

export interface ParseQuestionsResponse {
  valid_questions: ParsedQuestion[];
  invalid_questions: ParsedQuestion[];
  errors: ParseQuestionsError[];
  total_blocks: number;
  valid_count: number;
  error_count: number;
  normalized_answer_key?: string | null;
  page_dimensions?: Array<[number, number]>;
  ocr_used?: boolean;
}

export interface ExamResultsSummary {
  completed_attempts: number;
  average_percentage: DecimalValue | null;
  highest_percentage: DecimalValue | null;
  lowest_percentage: DecimalValue | null;
  pass_rate: DecimalValue | null;
}

export interface ExamAdminAttemptRow {
  attempt_id: string;
  user_id: string;
  email: string | null;
  display_name: string | null;
  status: string;
  submission_reason: string | null;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered_questions: number;
  points_earned: DecimalValue;
  points_available: DecimalValue;
  percentage: DecimalValue;
  passed: boolean;
}

export interface ExamAdminResultsResponse {
  exam_id: string;
  exam_title: string;
  pass_mark: DecimalValue;
  total_attempts: number;
  summary: ExamResultsSummary;
  attempts: ExamAdminAttemptRow[];
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
  points_earned: DecimalValue;
  points_available: DecimalValue;
  options: AttemptQuestionReviewOption[];
}

export interface AttemptResultOut {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  status: string;
  submission_reason: string | null;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  total_questions: number;
  correct_answers: number;
  incorrect_answers: number;
  unanswered_questions: number;
  points_earned: DecimalValue;
  points_available: DecimalValue;
  percentage: DecimalValue;
  pass_mark: DecimalValue;
  passed: boolean;
  result_visible: true;
  show_correct_answers: boolean;
  question_review: AttemptQuestionReviewItem[] | null;
  student_user_id: string | null;
  student_email: string | null;
  student_display_name: string | null;
}
