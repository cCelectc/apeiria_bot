"""Add meta_json and raw_data_json columns to chat_message.

Revision ID: 0007_add_chat_message_meta_and_raw_data
Revises: 0006_reconcile_legacy_schema
Create Date: 2026-06-17
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "0007_add_chat_message_meta_and_raw_data"
down_revision: str | None = "0006_reconcile_legacy_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _col_exists(conn: sa.engine.Connection, table: str, col: str) -> bool:
    rows = conn.execute(sa.text(f"PRAGMA table_info({table})"))
    return any(row[1] == col for row in rows)


def upgrade() -> None:
    conn: sa.engine.Connection = op.get_bind()

    if not _col_exists(conn, "chat_message", "meta_json"):
        op.execute(sa.text("ALTER TABLE chat_message ADD COLUMN meta_json TEXT"))
    if not _col_exists(conn, "chat_message", "raw_data_json"):
        op.execute(sa.text("ALTER TABLE chat_message ADD COLUMN raw_data_json TEXT"))


def downgrade() -> None:
    pass
