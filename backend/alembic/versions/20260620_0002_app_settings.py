"""Add persistent application settings.

Revision ID: 20260620_0002
Revises: 20260619_0001
Create Date: 2026-06-20
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260620_0002"
down_revision: str | None = "20260619_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    if "app_settings" in sa.inspect(bind).get_table_names():
        return
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if "app_settings" in sa.inspect(bind).get_table_names():
        op.drop_table("app_settings")