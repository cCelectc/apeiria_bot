"""Runtime media preparation for provider-neutral model input."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from apeiria.ai.model import AIModelContentPart

if TYPE_CHECKING:
    from apeiria.app.ai.runtime.session.context import RuntimeSourceMediaPart


@dataclass(frozen=True, slots=True)
class RuntimePreparedMediaResult:
    """Prepared model-visible media parts with bounded diagnostics."""

    parts: tuple[AIModelContentPart, ...] = ()
    diagnostics: tuple[dict[str, object], ...] = ()


@dataclass(frozen=True, slots=True)
class _ResolvedAsset:
    data: bytes | None = None
    url: str | None = None
    mime_type: str | None = None
    file_name: str | None = None
    size_bytes: int | None = None


def prepare_runtime_media_parts(
    media_parts: tuple["RuntimeSourceMediaPart", ...],
) -> RuntimePreparedMediaResult:
    """Resolve safe runtime media references into model content parts."""

    prepared: list[AIModelContentPart] = []
    diagnostics: list[dict[str, object]] = []
    for media in media_parts:
        part, diagnostic = _prepare_one(media)
        if part is not None:
            prepared.append(part)
            diagnostics.append(_diagnostic(media, status="prepared"))
        elif diagnostic is not None:
            diagnostics.append(diagnostic)
    return RuntimePreparedMediaResult(
        parts=tuple(prepared),
        diagnostics=tuple(diagnostics),
    )


def resolve_runtime_media_part(
    media: "RuntimeSourceMediaPart",
) -> tuple[AIModelContentPart | None, dict[str, object] | None]:
    """Resolve one runtime media reference into a model content part."""

    return _prepare_one(media)


def _prepare_one(
    media: "RuntimeSourceMediaPart",
) -> tuple[AIModelContentPart | None, dict[str, object] | None]:
    metadata = media.safe_metadata()
    if media.url:
        return (
            AIModelContentPart(
                kind=media.kind,
                url=media.url,
                mime_type=media.mime_type,
                metadata=metadata or None,
                required=media.required,
            ),
            None,
        )

    data = _decode_base64(media.base64_data or _base64_file_ref(media.file_ref))
    source_kind = "base64"
    if data is None:
        resolved_path = _resolve_path(media)
        if resolved_path is not None:
            try:
                data = resolved_path.read_bytes()
            except OSError:
                data = None
            else:
                source_kind = "local_file"
                metadata = {
                    **metadata,
                    "file_name": media.file_name or resolved_path.name,
                    "size_bytes": len(data),
                }

    if data is not None:
        return (
            AIModelContentPart(
                kind=media.kind,
                data=data,
                mime_type=media.mime_type or _guess_mime(media),
                metadata={**metadata, "source_kind": source_kind}
                if metadata
                else {"source_kind": source_kind},
                required=media.required,
            ),
            None,
        )

    if media.asset_id:
        asset = _resolve_chat_asset(media.asset_id)
        if asset is not None:
            asset_metadata = {
                **metadata,
                **(
                    {"file_name": asset.file_name}
                    if asset.file_name and "file_name" not in metadata
                    else {}
                ),
                **(
                    {"size_bytes": asset.size_bytes}
                    if asset.size_bytes is not None and "size_bytes" not in metadata
                    else {}
                ),
                "source_kind": "asset",
            }
            return (
                AIModelContentPart(
                    kind=media.kind,
                    url=asset.url,
                    data=asset.data,
                    mime_type=media.mime_type or asset.mime_type,
                    metadata=asset_metadata,
                    required=media.required,
                ),
                None,
            )

    return None, _diagnostic(media, status="unresolved", reason="unresolved_reference")


def _resolve_path(media: "RuntimeSourceMediaPart") -> Path | None:
    for value in (media.path_ref, media.file_ref):
        if not value:
            continue
        if value.startswith("base64://"):
            continue
        path = Path(value)
        if path.is_file():
            return path
    return None


def _decode_base64(value: str | None) -> bytes | None:
    if not value:
        return None
    raw = value.removeprefix("base64://")
    try:
        return base64.b64decode(raw, validate=True)
    except ValueError:
        return None


def _base64_file_ref(value: str | None) -> str | None:
    if isinstance(value, str) and value.startswith("base64://"):
        return value
    return None


def _resolve_chat_asset(asset_id: str) -> _ResolvedAsset | None:
    asset = _get_chat_asset(asset_id)
    if asset is None:
        return None

    content_type = _asset_str(asset, "content_type")
    file_name = _asset_str(asset, "file_name")
    remote_url = _asset_str(asset, "remote_url")
    if remote_url:
        return _ResolvedAsset(
            url=remote_url,
            mime_type=content_type,
            file_name=file_name,
        )
    return _resolve_local_chat_asset(
        asset,
        content_type=content_type,
        file_name=file_name,
    )


def _get_chat_asset(asset_id: str) -> Any | None:
    try:
        from apeiria.app.chat.service import web_chat_service
    except Exception:  # noqa: BLE001
        return None

    try:
        asset = web_chat_service.get_asset(asset_id)
    except Exception:  # noqa: BLE001
        return None
    return asset


def _resolve_local_chat_asset(
    asset: Any,
    *,
    content_type: str | None,
    file_name: str | None,
) -> _ResolvedAsset | None:
    local_path = getattr(asset, "local_path", None)
    if isinstance(local_path, Path) and local_path.is_file():
        try:
            data = local_path.read_bytes()
        except OSError:
            return None
        return _ResolvedAsset(
            data=data,
            mime_type=content_type
            or _guess_mime_from_name(file_name or local_path.name),
            file_name=file_name or local_path.name,
            size_bytes=len(data),
        )
    return None


def _asset_str(asset: Any, field_name: str) -> str | None:
    value = getattr(asset, field_name, None)
    return value if isinstance(value, str) and value.strip() else None


def _guess_mime(media: "RuntimeSourceMediaPart") -> str | None:
    name = media.file_name or media.path_ref or media.file_ref
    if not name:
        return None
    return _guess_mime_from_name(name)


def _guess_mime_from_name(name: str) -> str | None:
    guessed, _encoding = mimetypes.guess_type(name)
    return guessed


def _diagnostic(
    media: "RuntimeSourceMediaPart",
    *,
    status: str,
    reason: str | None = None,
) -> dict[str, object]:
    diagnostic: dict[str, object] = {
        "status": status,
        "kind": media.kind,
    }
    if reason:
        diagnostic["reason"] = reason
    if media.mime_type:
        diagnostic["mime_type"] = media.mime_type
    if media.file_name:
        diagnostic["file_name"] = media.file_name
    if media.size_bytes is not None:
        diagnostic["size_bytes"] = media.size_bytes
    return diagnostic


__all__ = [
    "RuntimePreparedMediaResult",
    "prepare_runtime_media_parts",
    "resolve_runtime_media_part",
]
