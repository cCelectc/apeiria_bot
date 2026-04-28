from __future__ import annotations

"""Compatibility wrapper for the bot runtime entrypoint."""

import sys
from pathlib import Path

from apeiria.bot.entry import run
from apeiria.runtime.entry_guard import EntryEnvironmentError

if __name__ == "__main__":
    try:
        run(project_root=Path(__file__).resolve().parent)
    except EntryEnvironmentError as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1) from None
