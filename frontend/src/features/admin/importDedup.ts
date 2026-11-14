/** Keep one editor entry per question in a PDF source. Other uploads remain additive. */
export function uniqueIncomingPdfQuestions<
  T extends { source_file_id?: string | null; source_number?: number | null },
>(existingQuestions: T[], incomingQuestions: T[]): T[] {
  const seen = new Set(
    existingQuestions
      .filter((question) => question.source_file_id && question.source_number)
      .map((question) => `${question.source_file_id}:${question.source_number}`),
  );
  return incomingQuestions.filter((question) => {
    if (!question.source_file_id || !question.source_number) return true;
    const key = `${question.source_file_id}:${question.source_number}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
