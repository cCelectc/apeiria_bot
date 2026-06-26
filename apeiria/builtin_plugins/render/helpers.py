from __future__ import annotations

from typing import TYPE_CHECKING

from markdown_it import MarkdownIt

from .service import RenderOptions

if TYPE_CHECKING:
    from collections.abc import Sequence

_markdown = MarkdownIt("commonmark", {"breaks": True, "html": False}).enable("table")


def _normalized_wait_until(value: str) -> str:
    allowed = {"commit", "domcontentloaded", "load", "networkidle"}
    normalized = value.strip().lower()
    if normalized in allowed:
        return normalized
    return "networkidle"


def _build_options(  # noqa: PLR0913
    *,
    width: int | None = None,
    height: int | None = None,
    max_width: int | None = None,
    timeout_ms: int | None = None,
    wait_until: str = "networkidle",
    selector: str | None = None,
    full_page: bool = False,
    device_scale_factor: float | None = None,
    css_urls: Sequence[str] | None = None,
    inline_style: str = "",
    extra_head_html: str = "",
    base_url: str = "",
    settle_time_ms: int = 0,
) -> RenderOptions:
    return RenderOptions(
        width=max_width or width,
        height=height,
        timeout_ms=timeout_ms,
        wait_until=_normalized_wait_until(wait_until),  # type: ignore[arg-type]
        selector=selector,
        full_page=full_page,
        device_scale_factor=device_scale_factor,
        css_urls=list(css_urls or ()),
        inline_style=inline_style,
        extra_head_html=extra_head_html,
        base_url=base_url,
        settle_time_ms=settle_time_ms,
    )
