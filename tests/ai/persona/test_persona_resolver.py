from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


def test_resolve_default(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.persona.resolver import resolve
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_persona import Persona

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                db.add(
                    Persona(
                        name="default", prompt="I am default", enabled=1, is_default=1
                    )
                )
                await db.commit()
            result = await resolve("any_session")
            assert result is not None
            assert result.name == "default"

    asyncio.run(_run())


def test_resolve_binding_overrides_default(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.persona.resolver import resolve
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_persona import Persona, PersonaBinding

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                db.add(
                    Persona(name="default", prompt="default", enabled=1, is_default=1)
                )
                p2 = Persona(
                    name="tsundere",
                    prompt="tsundere prompt",
                    enabled=1,
                    is_default=0,
                )
                db.add(p2)
                await db.commit()
                await db.refresh(p2)
                db.add(PersonaBinding(session_id="s1", persona_id=p2.id))
                await db.commit()
            result = await resolve("s1")
            assert result is not None
            assert result.name == "tsundere"

    asyncio.run(_run())


def test_resolve_no_persona(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.persona.resolver import resolve

        async with async_db(tmp_path / "test.db"):
            result = await resolve("any_session")
            assert result is None

    asyncio.run(_run())
