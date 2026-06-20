from __future__ import annotations

import sys
import types
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent.parent / "apeiria" / "ai"
_ROUTING_PATH = _BASE / "model" / "routing"

if "apeiria.ai.model.routing" not in sys.modules:
    _stub = types.ModuleType("apeiria.ai.model.routing")
    _stub.__path__ = [str(_ROUTING_PATH)]
    _stub.__package__ = "apeiria.ai.model.routing"
    sys.modules["apeiria.ai.model.routing"] = _stub

import asyncio
from typing import TYPE_CHECKING

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def _seed_source(db: AsyncSession) -> None:
    from apeiria.db.models.ai_source import AISource

    db.add(
        AISource(
            source_id="src1",
            name="Test Source",
            adapter="openai_compatible",
        )
    )


def test_resolve_model_default(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.model.routing.resolve import resolve_model
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings
        from apeiria.db.models.ai_source import AIChatModel

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                _seed_source(db)
                await db.flush()
                db.add(
                    AIChatModel(
                        model_id="gpt-4",
                        source_id="src1",
                        model_identifier="gpt-4",
                        display_name="GPT-4",
                        enabled=1,
                    )
                )
                db.add(AIRuntimeSettings(id=1, default_chat_model="gpt-4"))
                await db.commit()

            model = await resolve_model("some:session:id")
            assert model is not None
            assert model.model_id == "gpt-4"

    asyncio.run(_run())


def test_resolve_model_override(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.model.routing.resolve import resolve_model
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings
        from apeiria.db.models.ai_source import AIChatModel
        from apeiria.db.models.conversation import Session

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                _seed_source(db)
                await db.flush()
                db.add(
                    AIChatModel(
                        model_id="gpt-4",
                        source_id="src1",
                        model_identifier="gpt-4",
                        display_name="GPT-4",
                        enabled=1,
                    )
                )
                db.add(
                    AIChatModel(
                        model_id="claude",
                        source_id="src1",
                        model_identifier="claude-3",
                        display_name="Claude",
                        enabled=1,
                    )
                )
                db.add(AIRuntimeSettings(id=1, default_chat_model="gpt-4"))
                db.add(
                    Session(
                        id="test:private:123",
                        platform="test",
                        scene_type="private",
                        scene_id="123",
                        model_override="claude",
                    )
                )
                await db.commit()

            model = await resolve_model("test:private:123")
            assert model is not None
            assert model.model_id == "claude"

    asyncio.run(_run())


def test_resolve_model_dangling_override(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.model.routing.resolve import resolve_model
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings
        from apeiria.db.models.ai_source import AIChatModel
        from apeiria.db.models.conversation import Session

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                _seed_source(db)
                await db.flush()
                db.add(
                    AIChatModel(
                        model_id="gpt-4",
                        source_id="src1",
                        model_identifier="gpt-4",
                        display_name="GPT-4",
                        enabled=1,
                    )
                )
                db.add(AIRuntimeSettings(id=1, default_chat_model="gpt-4"))
                db.add(
                    Session(
                        id="test:private:456",
                        platform="test",
                        scene_type="private",
                        scene_id="456",
                        model_override="deleted_model",
                    )
                )
                await db.commit()

            model = await resolve_model("test:private:456")
            assert model is not None
            assert model.model_id == "gpt-4"

    asyncio.run(_run())


def test_resolve_model_no_model(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.model.routing.resolve import resolve_model
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                db.add(AIRuntimeSettings(id=1))
                await db.commit()

            model = await resolve_model("test:private:789")
            assert model is None

    asyncio.run(_run())
