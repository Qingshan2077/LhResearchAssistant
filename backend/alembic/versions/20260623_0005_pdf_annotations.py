"""Add PDF annotations.

Revision ID: 20260623_0005
Revises: 20260621_0004
Create Date: 2026-06-23
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260623_0005"
down_revision: str | None = "20260621_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "pdf_annotations" not in existing:
        op.create_table(
            "pdf_annotations",
            sa.Column("id", sa.String(length=36), primary_key=True),
            sa.Column("paper_id", sa.String(length=36), nullable=False),
            sa.Column("page_number", sa.Integer(), nullable=False),
            sa.Column("rects", sa.JSON(), nullable=True),
            sa.Column("highlighted_text", sa.Text(), nullable=True),
            sa.Column("color", sa.String(length=16), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("annotation_type", sa.String(length=16), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        )
        op.create_index("ix_pdf_annotations_paper_id", "pdf_annotations", ["paper_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    if "pdf_annotations" in existing:
        indexes = {index["name"] for index in sa.inspect(bind).get_indexes("pdf_annotations")}
        if "ix_pdf_annotations_paper_id" in indexes:
            op.drop_index("ix_pdf_annotations_paper_id", table_name="pdf_annotations")
        op.drop_table("pdf_annotations")
