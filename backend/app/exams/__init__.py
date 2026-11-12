"""Exams domain module boundary.

Future responsibility:
- Manage examination definitions (`exams`), parsed questions (`questions`), and
  multiple-choice options (`question_options`).
- Parse pasted question text into structured previewable drafts, configure duration
  and pass marks, and enforce answer-key (`is_correct`) isolation from student DTOs.
"""
