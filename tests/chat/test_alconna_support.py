from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from nonebot_plugin_alconna.uniseg.segment import Emoji, Text

from apeiria.chat.alconna import WebChatMessageExporter


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
