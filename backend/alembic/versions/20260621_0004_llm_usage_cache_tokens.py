"""Add cache token details to LLM usage.

Revision ID: 20260621_0004
Revises: 20260621_0003
Create Date: 2026-06-21
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260621_0004"
down_revision: str | None = "20260621_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("llm_usage")}
    if "cache_hit_tokens" not in columns:
        op.add_column("llm_usage", sa.Column("cache_hit_tokens", sa.Integer(), nullable=True))
    if "cache_miss_tokens" not in columns:
        op.add_column("llm_usage", sa.Column("cache_miss_tokens", sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("llm_usage")}
    with op.batch_alter_table("llm_usage") as batch_op:
        if "cache_miss_tokens" in columns:
            batch_op.drop_column("cache_miss_tokens")
        if "cache_hit_tokens" in columns:
            batch_op.drop_column("cache_hit_tokens")
