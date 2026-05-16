"""Package-resource prompt template loading."""

from __future__ import annotations

from functools import cache
from importlib.resources import files
from pathlib import PurePosixPath

_TEMPLATE_PACKAGE = "apeiria.ai.prompting.templates"
_UNSUPPORTED_TEMPLATE_PATH = "unsupported prompt template path"


@cache
def load_prompt_template(path: str) -> str:
    """Load one plain-text prompt template from package data."""

    parts = _template_path_parts(path)
    template = files(_TEMPLATE_PACKAGE).joinpath(*parts).read_text(encoding="utf-8")
    return template.strip()


def load_prompt_template_lines(path: str) -> tuple[str, ...]:
    """Load one prompt template as non-empty stripped lines."""

    return tuple(
        line.strip() for line in load_prompt_template(path).splitlines() if line.strip()
    )


def _template_path_parts(path: str) -> tuple[str, ...]:
    normalized = PurePosixPath(path.strip().lstrip("/"))
    parts = normalized.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(_UNSUPPORTED_TEMPLATE_PATH)
    return tuple(parts)
