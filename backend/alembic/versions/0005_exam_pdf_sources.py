"""Add source PDF records and optional question crop references.

Revision ID: 0005_exam_pdf_sources
Revises: 0004_exam_closed_at_and_indexes
"""

from alembic import op
import sqlalchemy as sa

revision = "0005_exam_pdf_sources"
down_revision = "0004_exam_closed_at_and_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_source_files",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "exam_id", sa.Uuid(), sa.ForeignKey("exams.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("page_count", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_exam_source_files_exam_id", "exam_source_files", ["exam_id"])
    op.add_column("questions", sa.Column("source_file_id", sa.Uuid(), nullable=True))
    op.add_column("questions", sa.Column("source_number", sa.Integer(), nullable=True))
    op.add_column("questions", sa.Column("image_regions", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("image_paths", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("pdf_options_text", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("pdf_warnings", sa.Text(), nullable=True))
    op.add_column("questions", sa.Column("pdf_confidence", sa.Numeric(3, 2), nullable=True))
    op.create_foreign_key(
        "fk_questions_source_file_id", "questions", "exam_source_files", ["source_file_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_questions_source_file_id", "questions", type_="foreignkey")
    op.drop_column("questions", "image_regions")
    op.drop_column("questions", "pdf_confidence")
    op.drop_column("questions", "pdf_warnings")
    op.drop_column("questions", "pdf_options_text")
    op.drop_column("questions", "image_paths")
    op.drop_column("questions", "source_number")
    op.drop_column("questions", "source_file_id")
    op.drop_index("ix_exam_source_files_exam_id", table_name="exam_source_files")
    op.drop_table("exam_source_files")
