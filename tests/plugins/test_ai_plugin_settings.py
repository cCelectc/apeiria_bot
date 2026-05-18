from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable


def test_builtin_ai_plugin_metadata_does_not_expose_runtime_settings(
    monkeypatch: Any,
) -> None:
    monkeypatch.setitem(
        sys.modules,
        "nonebot",
        SimpleNamespace(
            get_driver=lambda: SimpleNamespace(on_startup=lambda func: func),
            require=lambda _name: None,
        ),
    )
    monkeypatch.setitem(
        sys.modules,
        "nonebot.adapters",
        SimpleNamespace(Bot=object, Event=object),
    )
    monkeypatch.setitem(
        sys.modules,
        "nonebot.permission",
        SimpleNamespace(SUPERUSER=object()),
    )

    class FakePluginMetadata:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    monkeypatch.setitem(
        sys.modules,
        "nonebot.plugin",
        SimpleNamespace(
            PluginMetadata=FakePluginMetadata,
            inherit_supported_adapters=lambda _name: (),
        ),
    )

    class FakeMatcher:
        def handle(self) -> Callable[[Callable[..., object]], Callable[..., object]]:
            def decorator(func: Callable[..., object]) -> Callable[..., object]:
                return func

            return decorator

    monkeypatch.setitem(
        sys.modules,
        "nonebot.plugin.on",
        SimpleNamespace(
            on_command=lambda *args, **kwargs: FakeMatcher(),  # noqa: ARG005
            on_message=lambda *args, **kwargs: FakeMatcher(),  # noqa: ARG005
        ),
    )
    fake_ai_module = types.ModuleType("apeiria.app.ai")
    fake_ai_module.__path__ = []  # type: ignore[attr-defined]

    def handle_message_stub(*_args: object, **_kwargs: object) -> None:
        return None

    fake_ai_module.ai_application = SimpleNamespace(
        diagnostics=SimpleNamespace(get_runtime_status=lambda: None),
        lifecycle=SimpleNamespace(startup=lambda: None),
        runtime=SimpleNamespace(handle_message=handle_message_stub),
    )
    fake_ai_runtime_module = types.ModuleType("apeiria.app.ai.runtime")
    fake_ai_runtime_module.__path__ = []  # type: ignore[attr-defined]
    fake_contracts_module = types.ModuleType("apeiria.app.ai.runtime.contracts")

    class FakeRuntimeTraceContext:
        def __init__(self, **kwargs: object) -> None:
            self.__dict__.update(kwargs)

    fake_contracts_module.RuntimeTraceContext = FakeRuntimeTraceContext
    monkeypatch.setitem(sys.modules, "apeiria.app.ai", fake_ai_module)
    monkeypatch.setitem(
        sys.modules,
        "apeiria.app.ai.runtime",
        fake_ai_runtime_module,
    )
    monkeypatch.setitem(
        sys.modules,
        "apeiria.app.ai.runtime.contracts",
        fake_contracts_module,
    )
    sys.modules.pop("apeiria.builtin_plugins.ai", None)

    module = importlib.import_module("apeiria.builtin_plugins.ai")

    assert not hasattr(module.__plugin_meta__, "config")
    extra_config = module.__plugin_meta__.extra.get("config", {})
    assert extra_config.get("fields") == []
