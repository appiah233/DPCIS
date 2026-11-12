"""Attempts domain module boundary.

Future responsibility:
- Manage student examination sessions (`exam_attempts`), frozen question ordering
  (`attempt_questions`), idempotent autosaved responses (`student_answers`),
  authoritative server-side `started_at`/`expires_at` timing, backend grading,
  and per-student result isolation.
"""
