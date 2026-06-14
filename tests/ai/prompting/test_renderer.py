"""Tests for prompt rendering and region projection."""

from __future__ import annotations

from apeiria.ai.prompting.models import (
    PromptPacket,
    PromptPurpose,
    PromptSection,
)
from apeiria.ai.prompting.regions import (
    PromptRegionProjection,
    project_prompt_regions,
    prompt_region_diagnostics,
)
from apeiria.ai.prompting.renderer import render_flat, render_messages


def _make_packet(
    *,
    purpose: PromptPurpose = "reply_final",
    system: str = "You are a helpful assistant.",
    user: str = "Hello!",
) -> PromptPacket:
    return PromptPacket(
        purpose=purpose,
        sections=(
            PromptSection(role="system", name="persona", content=system),
            PromptSection(role="user", name="user_message", content=user),
        ),
    )


class TestRenderFlat:
    def test_renders_with_section_headers(self) -> None:
        packet = _make_packet()
        result = render_flat(packet)
        assert "persona" in result
        assert "user_message" in result
        assert "You are a helpful assistant" in result
        assert "Hello!" in result

    def test_empty_sections_omitted(self) -> None:
        packet = PromptPacket(
            purpose="reply_final",
            sections=(
                PromptSection(role="system", name="empty_sys", content=""),
                PromptSection(role="user", name="msg", content="Hi"),
            ),
        )
        result = render_flat(packet)
        assert "empty_sys" not in result
        assert "msg" in result


class TestRenderMessages:
    def test_produces_aimodel_messages(self) -> None:
        packet = _make_packet()
        messages = render_messages(packet)
        assert len(messages) == 2  # noqa: PLR2004
        assert messages[0].role == "system"
        assert "You are a helpful assistant" in messages[0].content
        assert messages[1].role == "user"
        assert "Hello!" in messages[1].content

    def test_omits_empty_sections(self) -> None:
        packet = PromptPacket(
            purpose="reply_final",
            sections=(
                PromptSection(role="system", name="a", content=""),
                PromptSection(role="user", name="b", content="x"),
            ),
        )
        messages = render_messages(packet)
        assert len(messages) == 1
        assert "x" in messages[0].content


class TestProjectRegions:
    def test_splits_stable_and_dynamic(self) -> None:
        packet = PromptPacket(
            purpose="reply_final",
            sections=(
                PromptSection(role="system", name="persona", content="Sys"),
                PromptSection(role="system", name="context", content="Ctx"),
                PromptSection(role="user", name="query", content="Q"),
            ),
        )
        proj = project_prompt_regions(packet, stable_section_names=["persona"])
        assert len(proj.stable) == 1
        assert proj.stable[0].name == "persona"
        assert len(proj.dynamic) == 2  # noqa: PLR2004

    def test_empty_packet(self) -> None:
        packet = PromptPacket(purpose="reply_final", sections=())
        proj = project_prompt_regions(packet, stable_section_names=())
        assert len(proj.stable) == 0
        assert len(proj.dynamic) == 0
        diag = prompt_region_diagnostics(proj)
        assert diag["total_section_count"] == 0


class TestPromptRegionProjection:
    def test_has_expected_fields(self) -> None:
        proj = PromptRegionProjection(
            purpose="reply_final",
            stable=(PromptSection(role="system", name="s", content="Sys"),),
            dynamic=(),
        )
        assert proj.stable[0].name == "s"
        assert proj.stable[0].role == "system"
