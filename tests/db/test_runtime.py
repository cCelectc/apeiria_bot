from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

from pytest import raises

from apeiria.db.runtime import ApeiriaDatabase

if TYPE_CHECKING:
    from pathlib import Path


def test_transaction_sync_starts_transaction_before_first_write(tmp_path: Path) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    database.ensure_ready()

    with database.transaction_sync() as connection:
        assert connection.in_transaction
        connection.execute(
            """
            INSERT INTO plugin_state (
                plugin_id,
                enabled,
                access_mode,
                protection_mode,
                updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("plugin.test", 1, "default_allow", "normal", 1765967400000),
        )

    with database.connect_sync() as connection:
        row = connection.execute(
            "SELECT plugin_id FROM plugin_state WHERE plugin_id = ?",
            ("plugin.test",),
        ).fetchone()
    assert row == ("plugin.test",)


def test_transaction_sync_acquires_write_lock_before_first_write(
    tmp_path: Path,
) -> None:
    database = ApeiriaDatabase(project_root=tmp_path)
    database.ensure_ready()

    with database.transaction_sync() as connection:
        assert connection.in_transaction
        contender = sqlite3.connect(database.database_path(), timeout=0)
        try:
            with raises(sqlite3.OperationalError, match="locked"):
                contender.execute("BEGIN IMMEDIATE")
        finally:
            contender.close()
