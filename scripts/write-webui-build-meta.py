#!/usr/bin/env python3
"""Write Web UI build metadata for the current project checkout."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    from apeiria.environment.frontend_build import write_frontend_build_meta

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--project-root",
        type=Path,
        default=repo_root,
        help="Apeiria project root containing the web workspace.",
    )
    args = parser.parse_args(argv)

    write_frontend_build_meta(args.project_root.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
