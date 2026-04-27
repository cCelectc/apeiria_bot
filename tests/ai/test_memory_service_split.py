from __future__ import annotations

import importlib
from pathlib import Path


def test_memory_service_delegates_storage_knowledge_and_summary_boundaries() -> None:
    project_root = Path(__file__).resolve().parents[2]
    service_source = (
        project_root / "apeiria" / "ai" / "memory" / "service.py"
    ).read_text(encoding="utf-8")

    for module_name in (
        "apeiria.ai.memory.contracts",
        "apeiria.ai.memory.repository",
        "apeiria.ai.memory.knowledge",
        "apeiria.ai.memory.summaries",
    ):
        importlib.import_module(module_name)

    assert "database_runtime" not in service_source
    assert "ai_memory_embedding_store" not in service_source
    assert "ai_model_facade" not in service_source
    assert "build_summary_memory_content" not in service_source
