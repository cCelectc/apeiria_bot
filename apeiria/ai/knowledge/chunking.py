from __future__ import annotations

_TARGET_MIN = 800
_TARGET_MAX = 1000
_SEPARATORS = ["\n\n", "\n", "。", " "]


def recursive_split(text: str) -> list[str]:
    """Split text into chunks of 800-1000 chars at natural boundaries."""
    chunks: list[str] = []
    _split_recursive(text, _SEPARATORS, chunks)
    return chunks


def _split_recursive(  # noqa: C901, PLR0912
    text: str,
    separators: list[str],
    chunks: list[str],
) -> None:
    if len(text) <= _TARGET_MAX:
        stripped = text.strip()
        if stripped:
            chunks.append(stripped)
        return

    if not separators:
        for i in range(0, len(text), _TARGET_MAX):
            chunk = text[i : i + _TARGET_MAX].strip()
            if chunk:
                chunks.append(chunk)
        return

    sep = separators[0]
    remaining_seps = separators[1:]
    parts = text.split(sep)

    current = ""
    for part in parts:
        candidate = current + sep + part if current else part
        if len(candidate) <= _TARGET_MAX:
            current = candidate
        elif current:
            if len(current) >= _TARGET_MIN:
                chunks.append(current.strip())
                current = part
            elif len(candidate) <= _TARGET_MAX * 2:
                _split_recursive(candidate, remaining_seps, chunks)
                current = ""
            else:
                chunks.append(current.strip())
                _split_recursive(part, remaining_seps, chunks)
                current = ""
        else:
            _split_recursive(part, remaining_seps, chunks)
            current = ""

    if current:
        stripped = current.strip()
        if stripped:
            if len(stripped) < _TARGET_MIN and chunks:
                prev = chunks.pop()
                merged = prev + sep + stripped
                if len(merged) <= _TARGET_MAX:
                    chunks.append(merged)
                else:
                    chunks.append(prev)
                    chunks.append(stripped)
            else:
                chunks.append(stripped)
