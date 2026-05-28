from __future__ import annotations

from typing import Any


def test_ai_wiring_uses_lazy_cached_properties() -> None:
    from apeiria.app.ai.wiring import AIWiring

    wiring = AIWiring()

    tool_service = wiring.tool_service
    assert tool_service is wiring.tool_service

    retrieval_service = wiring.retrieval_service
    assert retrieval_service is wiring.retrieval_service

    model_wiring = wiring.model
    assert model_wiring is wiring.model
    assert model_wiring.invoker is model_wiring.invoker


def test_ai_wiring_respects_constructor_overrides() -> None:
    from apeiria.app.ai.wiring import AIWiring

    fake_tool_service = object()
    fake_model = object()

    wiring = AIWiring(
        tool_service=fake_tool_service,  # type: ignore[arg-type]
        model=fake_model,  # type: ignore[arg-type]
    )

    assert wiring.tool_service is fake_tool_service
    assert wiring.model is fake_model


def test_model_wiring_respects_constructor_overrides() -> None:
    from apeiria.app.ai.model_wiring import AIModelWiring

    fake_source_service = object()
    fake_invoker = object()

    wiring = AIModelWiring(
        source_service=fake_source_service,  # type: ignore[arg-type]
        invoker=fake_invoker,  # type: ignore[arg-type]
    )

    assert wiring.source_service is fake_source_service
    assert wiring.invoker is fake_invoker


def test_importing_wiring_module_does_not_construct_services(
    monkeypatch: Any,
) -> None:
    import importlib
    import sys

    service_module = importlib.import_module("apeiria.ai.tools.service")
    original_init = service_module.AIToolService.__init__
    calls: list[str] = []

    def tracking_init(self: Any, *args: Any, **kwargs: Any) -> None:
        calls.append("tool_service")
        original_init(self, *args, **kwargs)

    monkeypatch.setattr(service_module.AIToolService, "__init__", tracking_init)
    sys.modules.pop("apeiria.app.ai.wiring", None)

    importlib.import_module("apeiria.app.ai.wiring")

    assert calls == []
