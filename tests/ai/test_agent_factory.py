from __future__ import annotations

import importlib.util
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

_resolve_fqn = "apeiria.ai.model.routing.resolve"
if _resolve_fqn not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _resolve_fqn, str(_ROUTING_PATH / "resolve.py")
    )
    assert _spec and _spec.loader
    _resolve_mod = importlib.util.module_from_spec(_spec)
    sys.modules[_resolve_fqn] = _resolve_mod
    _spec.loader.exec_module(_resolve_mod)

_routing_stub = sys.modules["apeiria.ai.model.routing"]
if not hasattr(_routing_stub, "resolve_model"):
    _routing_stub.resolve_model = sys.modules[_resolve_fqn].resolve_model  # type: ignore[attr-defined]

import asyncio

from tests.db_helpers import async_db


def test_build_agent_no_model(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.builtin_plugins.ai.agent_factory import build_agent
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                db.add(AIRuntimeSettings(id=1))
                await db.commit()

            agent = await build_agent("test:private:123")
            assert agent is None

    asyncio.run(_run())
