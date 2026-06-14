"""Tests for persona service and resolver."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from apeiria.ai.persona.models import (
    AIPersonaBindingTarget,
    AIPersonaCreateInput,
)
from apeiria.ai.persona.resolver import resolve_persona_binding
from apeiria.ai.persona.service import AIPersonaService
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.anyio
async def test_create_and_get_persona(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        service = AIPersonaService()
        persona = await service.create_persona(
            AIPersonaCreateInput(
                name="TestBot",
                description="A test persona",
                system_prompt="You are helpful.",
                style_prompt="Be friendly.",
            )
        )
        assert persona.persona_id.startswith("persona_")
        assert persona.enabled is True

        found = await service.get_persona(persona_id=persona.persona_id)
        assert found is not None
        assert found.name == "TestBot"
        assert found.system_prompt == "You are helpful."


@pytest.mark.anyio
async def test_list_personas(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        service = AIPersonaService()
        await service.create_persona(
            AIPersonaCreateInput(
                name="Bot1",
                description="desc1",
                system_prompt="s1",
                style_prompt="sp1",
            )
        )
        await service.create_persona(
            AIPersonaCreateInput(
                name="Bot2",
                description="desc2",
                system_prompt="s2",
                style_prompt="sp2",
                enabled=False,
            )
        )
        all_personas = await service.list_personas()
        assert len(all_personas) == 2  # noqa: PLR2004
        enabled_only = await service.list_personas(include_disabled=False)
        assert len(enabled_only) == 1


@pytest.mark.anyio
async def test_update_persona(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        service = AIPersonaService()
        persona = await service.create_persona(
            AIPersonaCreateInput(
                name="Old",
                description="old desc",
                system_prompt="old",
                style_prompt="old style",
            )
        )
        updated = await service.update_persona(
            persona_id=persona.persona_id,
            create_input=AIPersonaCreateInput(
                name="New",
                description="new desc",
                system_prompt="new",
                style_prompt="new style",
            ),
        )
        assert updated is not None
        assert updated.name == "New"
        assert updated.system_prompt == "new"


@pytest.mark.anyio
async def test_resolve_persona_no_binding(tmp_path: Path) -> None:
    async with async_db(tmp_path / "test.db"):
        service = AIPersonaService()
        target = AIPersonaBindingTarget(
            conversation_id="c1", group_id=None, user_id="u1"
        )
        resolved = await service.resolve_persona(target=target)
        assert resolved is None


class TestResolverPure:
    def test_matches_binding_by_user(self) -> None:
        from apeiria.ai.persona.models import AIPersonaBindingSpec

        bindings = (
            AIPersonaBindingSpec(
                binding_id="b1",
                scope_type="user",
                scope_id="u1",
                persona_id="p1",
            ),
        )
        target = AIPersonaBindingTarget(
            conversation_id="c1", group_id=None, user_id="u1"
        )
        result = resolve_persona_binding(bindings=bindings, target=target)
        assert result is not None
        assert result.persona_id == "p1"

    def test_no_match_returns_none(self) -> None:
        from apeiria.ai.persona.models import AIPersonaBindingSpec

        bindings = (
            AIPersonaBindingSpec(
                binding_id="b1",
                scope_type="group",
                scope_id="g1",
                persona_id="p1",
            ),
        )
        target = AIPersonaBindingTarget(
            conversation_id="c1", group_id="g2", user_id="u1"
        )
        assert resolve_persona_binding(bindings=bindings, target=target) is None
