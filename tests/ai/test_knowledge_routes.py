from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apeiria.db.runtime import database_runtime
from apeiria.webui.auth import require_control_panel

HTTP_OK = 200
HTTP_BAD_REQUEST = 400
EXPECTED_CHUNK_COUNT = 2

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_knowledge_routes_validate_and_preview_without_live_turns(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.webui.routes.ai import router

    def dependency_override() -> object:
        return object()

    app = FastAPI()
    app.dependency_overrides[require_control_panel] = dependency_override
    app.include_router(router, prefix="/ai")
    client = TestClient(app)

    state = client.get("/ai/knowledge/state")
    assert state.status_code == HTTP_OK
    assert state.json()["rag_enabled"] is False

    updated_state = client.patch("/ai/knowledge/state", json={"rag_enabled": True})
    assert updated_state.status_code == HTTP_OK
    assert updated_state.json()["rag_enabled"] is True

    rejected = client.post(
        "/ai/knowledge/documents",
        json={"source_file_name": "manual.pdf", "content": "not supported"},
    )
    assert rejected.status_code == HTTP_BAD_REQUEST
    assert "unsupported_file_type" in rejected.json()["detail"]

    uploaded = client.post(
        "/ai/knowledge/documents",
        json={
            "source_file_name": "manual.md",
            "content": "# Manual\n\nRAG route preview uses chunks.",
        },
    )
    assert uploaded.status_code == HTTP_OK
    uploaded_payload = uploaded.json()
    assert uploaded_payload["document"]["title"] == "manual"
    assert uploaded_payload["diagnostics"]["processed_count"] == 0
    assert uploaded_payload["diagnostics"]["skipped_count"] == EXPECTED_CHUNK_COUNT

    documents = client.get("/ai/knowledge/documents")
    assert documents.status_code == HTTP_OK
    document_id = documents.json()[0]["document_id"]

    chunks = client.get(f"/ai/knowledge/documents/{document_id}/chunks")
    assert chunks.status_code == HTTP_OK
    assert len(chunks.json()) == EXPECTED_CHUNK_COUNT
    assert "RAG route preview" in chunks.json()[1]["text"]

    preview = client.post(
        "/ai/knowledge/retrieval/preview",
        json={"query_text": "RAG preview", "limit": 1},
    )
    assert preview.status_code == HTTP_OK
    assert preview.json()["items"][0]["label"] == "K1"
    assert preview.json()["diagnostics"]["selected_count"] == 1

    deleted = client.delete(f"/ai/knowledge/documents/{document_id}")
    assert deleted.status_code == HTTP_OK
    assert deleted.json() == {"deleted": True}
