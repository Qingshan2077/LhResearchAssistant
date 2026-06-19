"""Initial application schema.

Revision ID: 20260619_0001
Revises:
Create Date: 2026-06-19
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260619_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names()) - {"alembic_version"}
    if existing_tables:
        if "papers" in existing_tables:
            paper_columns = {column["name"] for column in inspector.get_columns("papers")}
            additions = [
                ("pdf_download_error", sa.Column("pdf_download_error", sa.Text(), server_default="")),
                ("citation_verified", sa.Column("citation_verified", sa.JSON(), server_default="[]")),
                ("citation_data", sa.Column("citation_data", sa.Text(), server_default="")),
                ("citation_cached_at", sa.Column("citation_cached_at", sa.DateTime(), nullable=True)),
            ]
            with op.batch_alter_table("papers") as batch_op:
                for name, column in additions:
                    if name not in paper_columns:
                        batch_op.add_column(column)
        if "llm_providers" in existing_tables:
            provider_columns = {
                column["name"] for column in inspector.get_columns("llm_providers")
            }
            additions = [
                ("last_test_at", sa.Column("last_test_at", sa.DateTime(), nullable=True)),
                (
                    "last_test_success",
                    sa.Column("last_test_success", sa.Boolean(), nullable=True),
                ),
                (
                    "last_test_latency",
                    sa.Column("last_test_latency", sa.Integer(), server_default="0"),
                ),
            ]
            with op.batch_alter_table("llm_providers") as batch_op:
                for name, column in additions:
                    if name not in provider_columns:
                        batch_op.add_column(column)
        return

    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=True),
        sa.Column("api_key", sa.String(length=1024), nullable=True),
        sa.Column("base_url", sa.String(length=512), nullable=True),
        sa.Column("default_model", sa.String(length=128), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=True),
        sa.Column("max_tokens", sa.Integer(), nullable=True),
        sa.Column("temperature", sa.Float(), nullable=True),
        sa.Column("last_test_at", sa.DateTime(), nullable=True),
        sa.Column("last_test_success", sa.Boolean(), nullable=True),
        sa.Column("last_test_latency", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("provider_id", sa.String(length=36), nullable=True),
        sa.Column("provider_name", sa.String(length=64), nullable=True),
        sa.Column("model", sa.String(length=128), nullable=True),
        sa.Column("function_name", sa.String(length=64), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=True),
        sa.Column("error_msg", sa.String(length=512), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_llm_usage_timestamp"), "llm_usage", ["timestamp"], unique=False)
    op.create_table(
        "papers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("title", sa.String(length=1024), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=True),
        sa.Column("abstract", sa.Text(), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("venue", sa.String(length=512), nullable=True),
        sa.Column("paper_type", sa.String(length=32), nullable=True),
        sa.Column("doi", sa.String(length=255), nullable=True),
        sa.Column("arxiv_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=True),
        sa.Column("keywords", sa.JSON(), nullable=True),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("pdf_url", sa.String(length=1024), nullable=True),
        sa.Column("pdf_path", sa.String(length=1024), nullable=True),
        sa.Column("pdf_download_error", sa.Text(), nullable=True),
        sa.Column("extracted_data", sa.JSON(), nullable=True),
        sa.Column("citation_verified", sa.JSON(), nullable=True),
        sa.Column("citation_data", sa.Text(), nullable=True),
        sa.Column("citation_cached_at", sa.DateTime(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("read_status", sa.String(length=16), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "search_histories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("query", sa.String(length=1024), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=True),
        sa.Column("result_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "writing_projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("target_venue", sa.String(length=256), nullable=True),
        sa.Column("language", sa.String(length=8), nullable=True),
        sa.Column("template", sa.String(length=128), nullable=True),
        sa.Column("external_editor_path", sa.String(length=1024), nullable=True),
        sa.Column("outline", sa.JSON(), nullable=True),
        sa.Column("latex_project_path", sa.String(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "paper_relations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_paper_id", sa.String(length=36), nullable=False),
        sa.Column("target_paper_id", sa.String(length=36), nullable=False),
        sa.Column("relation_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["source_paper_id"], ["papers.id"]),
        sa.ForeignKeyConstraint(["target_paper_id"], ["papers.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "mindmap_nodes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("paper_id", sa.String(length=36), nullable=False),
        sa.Column("parent_id", sa.String(length=36), nullable=True),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("node_type", sa.String(length=32), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("position_x", sa.Float(), nullable=True),
        sa.Column("position_y", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["paper_id"], ["papers.id"]),
        sa.ForeignKeyConstraint(["parent_id"], ["mindmap_nodes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("mindmap_nodes")
    op.drop_table("paper_relations")
    op.drop_table("writing_projects")
    op.drop_table("search_histories")
    op.drop_table("papers")
    op.drop_index(op.f("ix_llm_usage_timestamp"), table_name="llm_usage")
    op.drop_table("llm_usage")
    op.drop_table("llm_providers")
    op.drop_table("projects")
