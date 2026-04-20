"""Web UI frontend build metadata helpers."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

BUILD_META_FILENAME = ".build-meta.json"
BUILD_META_VERSION = 1


@dataclass(frozen=True)
class FrontendBuildStatus:
    """Frontend build fingerprint comparison result."""

    is_built: bool
    is_stale: bool
    detail: str


def web_dir(project_root: Path) -> Path:
    return project_root / "web"


def dist_dir(project_root: Path) -> Path:
    return web_dir(project_root) / "dist"


def build_meta_path(project_root: Path) -> Path:
    return dist_dir(project_root) / BUILD_META_FILENAME


def compute_frontend_fingerprint(project_root: Path) -> str:
    root = web_dir(project_root)
    digest = hashlib.sha256()
    for path in _fingerprint_inputs(root):
        if not path.exists():
            continue
        if path.is_file():
            _update_digest_for_file(digest, root, path)
            continue
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            _update_digest_for_file(digest, root, child)
    return digest.hexdigest()


def read_frontend_build_status(project_root: Path) -> FrontendBuildStatus:
    dist = dist_dir(project_root)
    if not dist.is_dir():
        return FrontendBuildStatus(
            is_built=False,
            is_stale=True,
            detail="dist_missing",
        )

    meta = _read_build_meta(project_root)
    if meta is None:
        return FrontendBuildStatus(
            is_built=True,
            is_stale=True,
            detail="build_meta_missing",
        )

    current = compute_frontend_fingerprint(project_root)
    built = str(meta.get("fingerprint") or "")
    if not built:
        return FrontendBuildStatus(
            is_built=True,
            is_stale=True,
            detail="fingerprint_missing",
        )

    return FrontendBuildStatus(
        is_built=True,
        is_stale=current != built,
        detail="stale" if current != built else "current",
    )


def write_frontend_build_meta(project_root: Path) -> None:
    meta_path = build_meta_path(project_root)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": BUILD_META_VERSION,
        "fingerprint": compute_frontend_fingerprint(project_root),
    }
    meta_path.write_text(
        json.dumps(payload, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _read_build_meta(project_root: Path) -> dict[str, object] | None:
    meta_path = build_meta_path(project_root)
    if not meta_path.is_file():
        return None
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _fingerprint_inputs(root: Path) -> tuple[Path, ...]:
    return (
        root / "src",
        root / "public",
        root / "index.html",
        root / "package.json",
        root / "pnpm-lock.yaml",
        root / "vite.config.mts",
    )


def _update_digest_for_file(
    digest: "hashlib._Hash",
    root: Path,
    path: Path,
) -> None:
    digest.update(path.relative_to(root).as_posix().encode("utf-8"))
    digest.update(b"\0")
    digest.update(path.read_bytes())
    digest.update(b"\0")
