"""Small file-backed settings for default knowledge-base RAG."""

from __future__ import annotations

import json
from dataclasses import dataclass

from apeiria.db.runtime import database_runtime


@dataclass(frozen=True)
class KnowledgeSettings:
    """Operator-facing RAG settings for the default knowledge base."""

    rag_enabled: bool = False


def _settings_path():
    return database_runtime.project_root / "data" / "ai" / "knowledge_settings.json"


class KnowledgeSettingsStore:
    """Persist the explicit RAG enable switch outside runtime state."""

    def get(self) -> KnowledgeSettings:
        target = _settings_path()
        if not target.is_file():
            return KnowledgeSettings()
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return KnowledgeSettings()
        if not isinstance(payload, dict):
            return KnowledgeSettings()
        return KnowledgeSettings(rag_enabled=bool(payload.get("rag_enabled", False)))

    def set_rag_enabled(self, *, enabled: bool) -> KnowledgeSettings:
        settings = KnowledgeSettings(rag_enabled=enabled)
        target = _settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp_target = target.with_suffix(".tmp")
        tmp_target.write_text(
            json.dumps({"rag_enabled": settings.rag_enabled}, sort_keys=True),
            encoding="utf-8",
        )
        tmp_target.replace(target)
        return settings


knowledge_settings_store = KnowledgeSettingsStore()
