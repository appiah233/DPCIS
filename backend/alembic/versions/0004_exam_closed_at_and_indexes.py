"""Add exams.closed_at, student_answers defaults, and query/integrity indexes.

Additive migration on top of 0003_attempt_option_order. Does not rewrite
historical migrations (0001-0003) or touch Neon Managed Auth tables.

Revision ID: 0004_exam_closed_at_and_indexes
Revises: 0003_attempt_option_order
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_exam_closed_at_and_indexes"
down_revision = "0003_attempt_option_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "exams",
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )

    with op.batch_alter_table("student_answers") as batch_op:
        batch_op.alter_column(
            "answered_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
        )
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            server_default=sa.func.now(),
        )

    op.create_index("ix_exams_status", "exams", ["status"], unique=False)
    op.create_index("ix_exams_created_by", "exams", ["created_by"], unique=False)
    op.create_index(
        "ix_questions_exam_id_position",
        "questions",
        ["exam_id", "position"],
        unique=False,
    )
    op.create_index(
        "ix_question_options_question_id",
        "question_options",
        ["question_id"],
        unique=False,
    )
    op.create_index(
        "uq_question_options_one_correct_per_question",
        "question_options",
        ["question_id"],
        unique=True,
        postgresql_where=sa.text("is_correct IS TRUE"),
        sqlite_where=sa.text("is_correct = 1"),
    )
    op.create_index(
        "ix_exam_attempts_user_id_exam_id",
        "exam_attempts",
        ["user_id", "exam_id"],
        unique=False,
    )
    op.create_index(
        "ix_exam_attempts_exam_id_status",
        "exam_attempts",
        ["exam_id", "status"],
        unique=False,
    )
    op.create_index(
        "uq_exam_attempts_active_user_exam",
        "exam_attempts",
        ["user_id", "exam_id"],
        unique=True,
        postgresql_where=sa.text("status = 'IN_PROGRESS'"),
        sqlite_where=sa.text("status = 'IN_PROGRESS'"),
    )
    op.create_index(
        "uq_attempt_questions_attempt_id_display_order",
        "attempt_questions",
        ["attempt_id", "display_order"],
        unique=True,
    )
    op.create_index(
        "ix_student_answers_attempt_id",
        "student_answers",
        ["attempt_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_student_answers_attempt_id", table_name="student_answers")
    op.drop_index(
        "uq_attempt_questions_attempt_id_display_order",
        table_name="attempt_questions",
    )
    op.drop_index("uq_exam_attempts_active_user_exam", table_name="exam_attempts")
    op.drop_index("ix_exam_attempts_exam_id_status", table_name="exam_attempts")
    op.drop_index("ix_exam_attempts_user_id_exam_id", table_name="exam_attempts")
    op.drop_index(
        "uq_question_options_one_correct_per_question",
        table_name="question_options",
    )
    op.drop_index("ix_question_options_question_id", table_name="question_options")
    op.drop_index("ix_questions_exam_id_position", table_name="questions")
    op.drop_index("ix_exams_created_by", table_name="exams")
    op.drop_index("ix_exams_status", table_name="exams")

    with op.batch_alter_table("student_answers") as batch_op:
        batch_op.alter_column(
            "updated_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.func.now(),
            server_default=None,
        )
        batch_op.alter_column(
            "answered_at",
            existing_type=sa.DateTime(timezone=True),
            existing_nullable=False,
            existing_server_default=sa.func.now(),
            server_default=None,
        )

    op.drop_column("exams", "closed_at")
