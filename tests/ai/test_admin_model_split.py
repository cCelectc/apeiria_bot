from __future__ import annotations

import importlib
from pathlib import Path


def test_model_admin_delegates_upstream_connectivity_checks() -> None:
    project_root = Path(__file__).resolve().parents[2]
    models_source = (
        project_root / "apeiria" / "app" / "ai" / "admin" / "models.py"
    ).read_text(encoding="utf-8")

    module = importlib.import_module("apeiria.app.ai.admin.model_connectivity")

    assert hasattr(module, "fetch_source_model_catalog")
    assert hasattr(module, "test_source_model_connectivity")
    assert "import wave" not in models_source
    assert "_build_test_wav_bytes" not in models_source
    assert "_sanitize_upstream_error_detail" not in models_source
    assert "generate_text_for_source" not in models_source
