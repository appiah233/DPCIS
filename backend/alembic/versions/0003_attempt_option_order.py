"""Add option_order column to attempt_questions for option randomization.

Additive migration on top of 0002_examination_schema. Stores the per-attempt,
per-question display order of options when randomize_options is enabled, so a
student's delivered examination can be reproduced exactly.

Revision ID: 0003_attempt_option_order
Revises: 0002_examination_schema
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_attempt_option_order"
down_revision = "0002_examination_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attempt_questions",
        sa.Column(
            "option_order",
            sa.Text(),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("attempt_questions", "option_order")
