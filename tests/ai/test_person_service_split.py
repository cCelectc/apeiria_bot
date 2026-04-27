from __future__ import annotations

import importlib
from pathlib import Path


def test_person_profile_service_delegates_sqlite_storage() -> None:
    project_root = Path(__file__).resolve().parents[2]
    service_source = (
        project_root / "apeiria" / "ai" / "person" / "service.py"
    ).read_text(encoding="utf-8")

    repository_module = importlib.import_module("apeiria.ai.person.repository")

    assert hasattr(repository_module, "PersonProfileRepository")
    assert "database_runtime" not in service_source
    assert "_SELECT_PROFILE_FIELDS" not in service_source
    assert "_row_to_person_profile" not in service_source
