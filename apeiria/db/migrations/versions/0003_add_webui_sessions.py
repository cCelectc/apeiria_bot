"""add webui_sessions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-23 00:00:00.000000
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "webui_sessions",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("webui_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.Text, nullable=False),
        sa.Column("last_active_at", sa.Text, nullable=False),
        sa.Column("revoked", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.Text, nullable=False),
        sa.CheckConstraint(
            "revoked IN (0, 1)",
            name="ck_webui_sessions_revoked",
        ),
    )


def downgrade() -> None:
    op.drop_table("webui_sessions")
