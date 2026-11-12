"""Add examination domain tables (exams, questions, options, attempts, answers).

Additive migration on top of 0001_application_users. Does not touch
Neon Managed Auth schema or the historical 0001 migration.

Revision ID: 0002_examination_schema
Revises: 0001_application_users
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0002_examination_schema"
down_revision = "0001_application_users"
branch_labels = None
depends_on = None

UUID_TYPE = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "exams",
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "pass_mark",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column("question_limit", sa.Integer(), nullable=True),
        sa.Column(
            "randomize_questions",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "randomize_options",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("show_result", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "show_correct_answers",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'DRAFT'"),
        ),
        sa.Column(
            "created_by",
            UUID_TYPE,
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "duration_minutes > 0", name="ck_exams_duration_minutes_positive"
        ),
        sa.CheckConstraint(
            "pass_mark >= 0 AND pass_mark <= 100", name="ck_exams_pass_mark_range"
        ),
        sa.CheckConstraint(
            "question_limit IS NULL OR question_limit > 0",
            name="ck_exams_question_limit_positive",
        ),
        sa.CheckConstraint("max_attempts >= 1", name="ck_exams_max_attempts_positive"),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'PUBLISHED', 'CLOSED')", name="ck_exams_status"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["application_users.id"],
        ),
        sa.PrimaryKeyConstraint("id", name="pk_exams"),
    )

    op.create_table(
        "questions",
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("exam_id", UUID_TYPE, nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "points",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text("1.00"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint("points > 0", name="ck_questions_points_positive"),
        sa.ForeignKeyConstraint(
            ["exam_id"],
            ["exams.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_questions"),
    )

    op.create_table(
        "question_options",
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("question_id", UUID_TYPE, nullable=False),
        sa.Column("label", sa.String(length=1), nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "label IN ('A', 'B', 'C', 'D')", name="ck_question_options_label_valid"
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_question_options"),
        sa.UniqueConstraint(
            "question_id", "label", name="uq_question_options_question_id_label"
        ),
    )

    op.create_table(
        "exam_attempts",
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("exam_id", UUID_TYPE, nullable=False),
        sa.Column("user_id", UUID_TYPE, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default=sa.text("'IN_PROGRESS'"),
        ),
        sa.Column("submission_reason", sa.String(length=16), nullable=True),
        sa.Column("total_questions", sa.Integer(), nullable=False),
        sa.Column("correct_answers", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("incorrect_answers", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "unanswered_questions",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "points_earned",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column(
            "points_available",
            sa.Numeric(precision=10, scale=2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column(
            "percentage",
            sa.Numeric(precision=5, scale=2),
            nullable=False,
            server_default=sa.text("0.00"),
        ),
        sa.Column("passed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('IN_PROGRESS', 'SUBMITTED', 'EXPIRED', 'GRADED')",
            name="ck_exam_attempts_status",
        ),
        sa.CheckConstraint(
            "submission_reason IS NULL OR "
            "submission_reason IN ('STUDENT_SUBMITTED', 'TIMER_EXPIRED')",
            name="ck_exam_attempts_submission_reason",
        ),
        sa.CheckConstraint(
            "total_questions >= 0", name="ck_exam_attempts_total_questions_nonneg"
        ),
        sa.CheckConstraint(
            "points_available >= 0", name="ck_exam_attempts_points_available_nonneg"
        ),
        sa.CheckConstraint(
            "points_earned >= 0", name="ck_exam_attempts_points_earned_nonneg"
        ),
        sa.CheckConstraint(
            "percentage >= 0 AND percentage <= 100", name="ck_exam_attempts_percentage_range"
        ),
        sa.ForeignKeyConstraint(["exam_id"], ["exams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["application_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_exam_attempts"),
    )

    op.create_table(
        "attempt_questions",
        sa.Column("attempt_id", UUID_TYPE, nullable=False),
        sa.Column("question_id", UUID_TYPE, nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "display_order >= 0", name="ck_attempt_questions_display_order_nonneg"
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["exam_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("attempt_id", "question_id", name="pk_attempt_questions"),
    )

    op.create_table(
        "student_answers",
        sa.Column("id", UUID_TYPE, nullable=False),
        sa.Column("attempt_id", UUID_TYPE, nullable=False),
        sa.Column("question_id", UUID_TYPE, nullable=False),
        sa.Column("selected_option_id", UUID_TYPE, nullable=True),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["exam_attempts.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["question_id"],
            ["questions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["selected_option_id"],
            ["question_options.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_answers"),
        sa.UniqueConstraint(
            "attempt_id", "question_id", name="uq_student_answers_attempt_id_question_id"
        ),
    )


def downgrade() -> None:
    op.drop_table("student_answers")
    op.drop_table("attempt_questions")
    op.drop_table("exam_attempts")
    op.drop_table("question_options")
    op.drop_table("questions")
    op.drop_table("exams")
