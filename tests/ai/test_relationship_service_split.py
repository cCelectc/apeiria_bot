from __future__ import annotations

import importlib
from pathlib import Path


def test_relationship_service_delegates_sqlite_storage() -> None:
    project_root = Path(__file__).resolve().parents[2]
    service_source = (
        project_root / "apeiria" / "ai" / "relationship" / "service.py"
    ).read_text(encoding="utf-8")

    repository_module = importlib.import_module("apeiria.ai.relationship.repository")

    assert hasattr(repository_module, "RelationshipRepository")
    assert "database_runtime" not in service_source
    assert "_row_to_affinity" not in service_source
    assert "_row_to_relationship_event" not in service_source
