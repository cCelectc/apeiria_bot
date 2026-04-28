from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from nonebot_plugin_alconna.uniseg.segment import Emoji, Text

from apeiria.app.chat import alconna
from apeiria.app.chat.alconna import WebChatMessageExporter


def test_webchat_exporter_non_event_send_is_explicitly_unsupported() -> None:
    exporter = WebChatMessageExporter()

    with pytest.raises(
        NotImplementedError,
        match="WebChat exporter only supports sends through event contexts",
    ):
        asyncio.run(
            exporter.send_to(
                object(),
                SimpleNamespace(),
                SimpleNamespace(),
            )
        )


def test_webchat_exporter_recall_is_explicitly_unsupported() -> None:
    exporter = WebChatMessageExporter()

    with pytest.raises(
        NotImplementedError,
        match="WebChat exporter does not support message recall",
    ):
        asyncio.run(exporter.recall("mid-1", SimpleNamespace(), object()))


def test_webchat_exporter_edit_is_explicitly_unsupported() -> None:
    exporter = WebChatMessageExporter()

    with pytest.raises(
        NotImplementedError,
        match="WebChat exporter does not support message editing",
    ):
        asyncio.run(
            exporter.edit(
                [Text("hi")],
                "mid-1",
                SimpleNamespace(),
                object(),
            )
        )


def test_webchat_exporter_reaction_is_explicitly_unsupported() -> None:
    exporter = WebChatMessageExporter()

    with pytest.raises(
        NotImplementedError,
        match="WebChat exporter does not support reactions",
    ):
        asyncio.run(
            exporter.reaction(
                Emoji("😀"),
                "mid-1",
                SimpleNamespace(),
                object(),
            )
        )


def test_register_webchat_uninfo_loads_plugin_before_importing_submodules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    adapters = SimpleNamespace(INFO_FETCHER_MAPPING={})
    fetcher = object()

    def fake_require(name: str) -> object:
        calls.append(("require", name))
        return object()

    def fake_import_module(name: str) -> object:
        calls.append(("import", name))
        if name != "nonebot_plugin_uninfo.adapters":
            raise AssertionError
        return adapters

    monkeypatch.setattr(alconna, "find_spec", lambda _name: object(), raising=False)
    monkeypatch.setattr(alconna, "require", fake_require, raising=False)
    monkeypatch.setattr(alconna, "import_module", fake_import_module)
    monkeypatch.setattr(alconna, "_build_webchat_uninfo_fetcher", lambda: fetcher)

    alconna.register_webchat_uninfo()

    assert calls == [
        ("require", "nonebot_plugin_uninfo"),
        ("import", "nonebot_plugin_uninfo.adapters"),
    ]
    assert adapters.INFO_FETCHER_MAPPING["WebChat"] is fetcher
