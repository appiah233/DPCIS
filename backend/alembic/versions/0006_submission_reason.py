"""Allow the full student submission reason in graded attempts.

Revision ID: 0006_submission_reason
Revises: 0005_exam_pdf_sources
"""

from alembic import op
import sqlalchemy as sa

revision = "0006_submission_reason"
down_revision = "0005_exam_pdf_sources"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "exam_attempts",
        "submission_reason",
        existing_type=sa.String(length=16),
        type_=sa.String(length=32),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "exam_attempts",
        "submission_reason",
        existing_type=sa.String(length=32),
        type_=sa.String(length=16),
        existing_nullable=True,
    )
