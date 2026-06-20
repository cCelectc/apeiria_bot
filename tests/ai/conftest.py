from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MODEL_BASE = _PROJECT_ROOT / "apeiria" / "ai" / "model"
_SKILLS_BASE = _PROJECT_ROOT / "apeiria" / "ai" / "skills"


def _load_direct(fqn: str, filepath: Path) -> types.ModuleType:
    spec = importlib.util.spec_from_file_location(fqn, str(filepath))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[fqn] = mod
    spec.loader.exec_module(mod)
    return mod


def _ensure_stub_package(fqn: str, base: Path) -> None:
    if fqn not in sys.modules:
        stub = types.ModuleType(fqn)
        stub.__path__ = [str(base)]
        stub.__package__ = fqn
        sys.modules[fqn] = stub


_ensure_stub_package("apeiria.ai.model", _MODEL_BASE)
_load_direct("apeiria.ai.model.exceptions", _MODEL_BASE / "exceptions.py")
_load_direct("apeiria.ai.model.registry", _MODEL_BASE / "registry.py")

_ensure_stub_package("apeiria.ai.skills", _SKILLS_BASE)
_load_direct("apeiria.ai.skills.catalog", _SKILLS_BASE / "catalog.py")
