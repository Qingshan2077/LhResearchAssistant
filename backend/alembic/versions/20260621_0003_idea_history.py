"""Add Socratic and idea generation history.

Revision ID: 20260621_0003
Revises: 20260620_0002
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260621_0003"
down_revision: str | None = "20260620_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "socratic_sessions" not in existing:
        op.create_table(
            "socratic_sessions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("intent", sa.String(length=32), nullable=True),
            sa.Column("layer", sa.Integer(), nullable=True),
            sa.Column("turn_count", sa.Integer(), nullable=True),
            sa.Column("is_converged", sa.Boolean(), nullable=True),
            sa.Column("summary_json", sa.JSON(), nullable=True),
            sa.Column("convergence_json", sa.JSON(), nullable=True),
            sa.Column("insights_list", sa.JSON(), nullable=True),
            sa.Column("layer_turns_json", sa.JSON(), nullable=True),
            sa.Column("rq_history_json", sa.JSON(), nullable=True),
            sa.Column("active_turn_index", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_socratic_sessions_project_id", "socratic_sessions", ["project_id"])

    if "socratic_messages" not in existing:
        op.create_table(
            "socratic_messages",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("role", sa.String(length=16), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["socratic_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_socratic_messages_session_id", "socratic_messages", ["session_id"])

    if "socratic_insights" not in existing:
        op.create_table(
            "socratic_insights",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("session_id", sa.String(length=36), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("turn_index", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["session_id"], ["socratic_sessions.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_socratic_insights_session_id", "socratic_insights", ["session_id"])

    if "idea_history" not in existing:
        op.create_table(
            "idea_history",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=True),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("mode", sa.String(length=32), nullable=False),
            sa.Column("paper_ids", sa.JSON(), nullable=True),
            sa.Column("custom_prompt", sa.Text(), nullable=True),
            sa.Column("domain_a", sa.String(length=128), nullable=True),
            sa.Column("domain_b", sa.String(length=128), nullable=True),
            sa.Column("generated_content", sa.Text(), nullable=True),
            sa.Column("evaluations", sa.JSON(), nullable=True),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_idea_history_project_id", "idea_history", ["project_id"])


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    for table, indexes in (
        ("socratic_insights", ["ix_socratic_insights_session_id"]),
        ("socratic_messages", ["ix_socratic_messages_session_id"]),
        ("idea_history", ["ix_idea_history_project_id"]),
        ("socratic_sessions", ["ix_socratic_sessions_project_id"]),
    ):
        if table not in existing:
            continue
        for index in indexes:
            op.drop_index(index, table_name=table)
        op.drop_table(table)
