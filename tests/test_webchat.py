from __future__ import annotations

from types import SimpleNamespace

import pytest

# ---------------------------------------------------------------------------
# message.py
# ---------------------------------------------------------------------------


def test_message_segment_factories_and_str() -> None:
    from apeiria.webchat.message import Message
    from apeiria.webchat.message import MessageSegment as Seg

    m = Message([Seg.text("hi"), Seg.image(url="u"), Seg.raw("at", {"qq": "1"})])
    assert str(m) == "hi[image][at]"
    assert m.extract_plain_text() == "hi"
    assert [s.type for s in m] == ["text", "image", "raw"]


def test_message_construct_from_str() -> None:
    from apeiria.webchat.message import Message

    assert Message("hello").extract_plain_text() == "hello"
    assert len(Message("")) == 0


def test_message_concat_with_str() -> None:
    from apeiria.webchat.message import MessageSegment as Seg

    combined = Seg.text("a") + "b"
    assert combined.extract_plain_text() == "ab"


# ---------------------------------------------------------------------------
# event.py
# ---------------------------------------------------------------------------


def _msg_event(
    scene_type: str, scene_id: str, user_id: str = "u1", *, to_me: bool = False
):
    from apeiria.webchat.event import WebChatMessageEvent
    from apeiria.webchat.message import Message
    from apeiria.webchat.message import MessageSegment as Seg

    return WebChatMessageEvent(
        time=1,
        self_id="webchat",
        message_id="m1",
        user_id=user_id,
        message=Message([Seg.text("hi")]),
        scene_type=scene_type,
        scene_id=scene_id,
        to_me=to_me,
    )


def test_event_session_id_private_and_group() -> None:
    assert _msg_event("private", "u1").get_session_id() == "webchat:private:u1"
    assert _msg_event("group", "g100").get_session_id() == "webchat:group:g100"


def test_event_basic_accessors() -> None:
    ev = _msg_event("private", "u1", to_me=True)
    assert ev.get_type() == "message"
    assert ev.get_user_id() == "u1"
    assert ev.get_plaintext() == "hi"
    assert ev.is_tome() is True
    assert ev.get_event_name() == "message.private"


def test_resolve_to_me_private_always_true() -> None:
    from apeiria.webchat.event import resolve_to_me
    from apeiria.webchat.message import Message
    from apeiria.webchat.message import MessageSegment as Seg

    assert resolve_to_me(Message([Seg.text("x")]), "private", []) is True


def test_resolve_to_me_group_nickname_strips() -> None:
    from apeiria.webchat.event import resolve_to_me
    from apeiria.webchat.message import Message
    from apeiria.webchat.message import MessageSegment as Seg

    msg = Message([Seg.text("Bot 你好")])
    assert resolve_to_me(msg, "group", ["Bot"]) is True
    assert msg.extract_plain_text() == "你好"


def test_resolve_to_me_group_without_nickname() -> None:
    from apeiria.webchat.event import resolve_to_me
    from apeiria.webchat.message import Message
    from apeiria.webchat.message import MessageSegment as Seg

    assert resolve_to_me(Message([Seg.text("随便说说")]), "group", ["Bot"]) is False


# ---------------------------------------------------------------------------
# protocol.py
# ---------------------------------------------------------------------------


def test_parse_inbound_variants() -> None:
    from apeiria.webchat import protocol as p

    assert isinstance(
        p.parse_inbound({"type": "message", "text": "hi"}), p.InboundMessage
    )
    assert isinstance(p.parse_inbound({"type": "clear"}), p.InboundClear)
    assert p.parse_inbound({"type": "delete", "message_id": "7"}).message_id == "7"
    assert isinstance(
        p.parse_inbound({"type": "switch", "identity": {"user_id": "u1"}}),
        p.InboundSwitch,
    )


def test_parse_inbound_errors() -> None:
    from apeiria.webchat import protocol as p

    for bad in ["x", {"type": "message"}, {"type": "delete"}, {"type": "nope"}]:
        with pytest.raises(p.ProtocolError):
            p.parse_inbound(bad)


def test_build_inbound_message_url_and_base64() -> None:
    from apeiria.webchat import protocol as p

    url_msg = p.build_inbound_message("hi", "http://x/i.png")
    assert [s.type for s in url_msg] == ["text", "image"]
    assert url_msg[1].data["url"] == "http://x/i.png"

    b64_msg = p.build_inbound_message("", "data:image/png;base64,AAAA")
    assert b64_msg[0].data["base64"] == "data:image/png;base64,AAAA"


def test_message_to_wire_all_segment_types() -> None:
    from apeiria.webchat import protocol as p
    from apeiria.webchat.message import Message
    from apeiria.webchat.message import MessageSegment as Seg

    wire = p.message_to_wire(
        Message([Seg.text("hi"), Seg.image(url="u"), Seg.raw("at", {"qq": "1"})])
    )
    assert wire == [
        {"type": "text", "text": "hi"},
        {"type": "image", "url": "u"},
        {"type": "raw", "seg_type": "at", "data": {"qq": "1"}},
    ]


def test_wire_message_and_frames() -> None:
    from apeiria.webchat import protocol as p

    wm = p.wire_message(
        message_id="1",
        role="bot",
        segments=[{"type": "text", "text": "hi"}],
        time="t",
        session_id="webchat:private:u1",
        user_id="webchat",
    )
    assert wm["id"] == "1"
    assert p.message_frame(wm) == {"type": "message", "message": wm}
    assert p.history_frame([wm], "webchat:private:u1")["type"] == "history"
    assert p.cleared_frame("webchat:private:u1") == {
        "type": "cleared",
        "session_id": "webchat:private:u1",
    }
    assert p.deleted_frame("9") == {"type": "deleted", "message_id": "9"}
    assert p.error_frame("c", "m") == {"type": "error", "code": "c", "message": "m"}


# ---------------------------------------------------------------------------
# connection.py
# ---------------------------------------------------------------------------


class _FakeWS:
    def __init__(self, *, fail: bool = False) -> None:
        self.sent: list = []
        self.fail = fail

    async def send_text(self, data: str) -> None:
        if self.fail:
            msg = "dead"
            raise RuntimeError(msg)
        import json

        self.sent.append(json.loads(data))


async def test_connection_route_and_broadcast() -> None:
    from apeiria.webchat.connection import ConnectionManager

    cm = ConnectionManager()
    a_ws, b_ws = _FakeWS(), _FakeWS()
    _, first_a = await cm.add(a_ws)
    b, first_b = await cm.add(b_ws)
    assert first_a is True
    assert first_b is False

    await cm.send_to(b, {"n": 1})
    assert b_ws.sent == [{"n": 1}]
    assert a_ws.sent == []

    await cm.broadcast({"bc": True})
    assert a_ws.sent == [{"bc": True}]
    assert b_ws.sent[-1] == {"bc": True}


async def test_connection_remove_reports_last_and_tolerates_dead() -> None:
    from apeiria.webchat.connection import ConnectionManager

    cm = ConnectionManager()
    a, _ = await cm.add(_FakeWS())
    dead, _ = await cm.add(_FakeWS(fail=True))
    await cm.send_to(dead, {"x": 1})  # must not raise
    assert await cm.remove(a) is False
    assert await cm.remove(dead) is True
    assert cm.count() == 0


# ---------------------------------------------------------------------------
# config.py
# ---------------------------------------------------------------------------


def _app(*, superusers: list[str], default_user_id: str = ""):
    from apeiria.config.models import (
        ApeiriaConfig,
        AppConfig,
        NoneBotConfig,
        WebChatConfig,
    )

    return AppConfig(
        nonebot=NoneBotConfig(superusers=superusers),
        apeiria=ApeiriaConfig(webchat=WebChatConfig(default_user_id=default_user_id)),
    )


def test_resolve_default_user_id_order() -> None:
    from apeiria.webchat.config import resolve_default_user_id

    assert resolve_default_user_id(_app(superusers=["s1"], default_user_id="x")) == "x"
    assert resolve_default_user_id(_app(superusers=["s1"])) == "s1"
    assert resolve_default_user_id(_app(superusers=[])) == "webchat-admin"


# ---------------------------------------------------------------------------
# bot.py
# ---------------------------------------------------------------------------


async def test_bot_send_routes_to_origin_and_persists(monkeypatch) -> None:
    from apeiria.conversation import store
    from apeiria.webchat.bot import WebChatBot
    from apeiria.webchat.connection import ConnectionManager

    calls: list = []

    async def fake_append(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(store, "append_message", fake_append)

    cm = ConnectionManager()
    ws = _FakeWS()
    conn, _ = await cm.add(ws)
    bot = WebChatBot(SimpleNamespace(), "webchat", cm)
    ev = _msg_event("private", "u1")
    ev.connection_id = conn

    await bot.send(ev, "hello")

    assert ws.sent[-1]["message"]["role"] == "bot"
    assert ws.sent[-1]["message"]["segments"] == [{"type": "text", "text": "hello"}]
    assert calls[0]["role"] == "bot"
    assert calls[0]["session_id"] == "webchat:private:u1"
    assert calls[0]["meta_json"]["segments"] == [{"type": "text", "text": "hello"}]


async def test_bot_send_broadcasts_without_connection(monkeypatch) -> None:
    from apeiria.conversation import store
    from apeiria.webchat.bot import WebChatBot
    from apeiria.webchat.connection import ConnectionManager

    async def noop(**_kwargs: object) -> None:
        return None

    monkeypatch.setattr(store, "append_message", noop)

    cm = ConnectionManager()
    ws1, ws2 = _FakeWS(), _FakeWS()
    await cm.add(ws1)
    await cm.add(ws2)
    bot = WebChatBot(SimpleNamespace(), "webchat", cm)
    ev = _msg_event("private", "u1")  # connection_id defaults to ""

    await bot.send(ev, "yo")
    assert len(ws1.sent) == 1
    assert len(ws2.sent) == 1


# ---------------------------------------------------------------------------
# uninfo.py
# ---------------------------------------------------------------------------


async def test_uninfo_fetch_private_and_group() -> None:
    from apeiria.webchat.uninfo import fetcher

    bot = SimpleNamespace(self_id="webchat")
    private = await fetcher.fetch(bot, _msg_event("private", "u1"))
    assert private.user.id == "u1"
    assert private.scene.id == "u1"
    assert private.scene.is_group is False

    group = await fetcher.fetch(bot, _msg_event("group", "g100", user_id="u9"))
    assert group.user.id == "u9"
    assert group.scene.id == "g100"
    assert group.scene.is_group is True
    assert group.member is not None


def test_register_uninfo_inserts_mapping() -> None:
    from apeiria.webchat.uninfo import register_uninfo

    register_uninfo()
    from nonebot_plugin_uninfo.adapters import INFO_FETCHER_MAPPING

    assert "WebChat" in INFO_FETCHER_MAPPING


# ---------------------------------------------------------------------------
# alconna.py
# ---------------------------------------------------------------------------


async def test_exporter_maps_text_and_image_to_dataurl() -> None:
    from nonebot_plugin_alconna.uniseg.segment import Image, Text

    from apeiria.webchat.alconna import WebChatExporter

    exp = WebChatExporter()
    assert sorted(t.__name__ for t in exp._mapping) == ["Image", "Text"]

    msg = await exp.export(
        [Text("hello"), Image(raw=b"\x89PNG\r\n\x1a\nXY", mimetype="image/png")],
        None,
        fallback=True,
    )
    types = [s.type for s in msg]
    assert "text" in types
    image_seg = next(s for s in msg if s.type == "image")
    assert image_seg.data["base64"].startswith("data:image/png;base64,")


def test_register_alconna_inserts_mappings() -> None:
    from apeiria.webchat.alconna import register_alconna

    register_alconna()
    from nonebot_plugin_alconna.uniseg.adapters import (
        BUILDER_MAPPING,
        EXPORTER_MAPPING,
    )

    assert "WebChat" in EXPORTER_MAPPING
    assert "WebChat" in BUILDER_MAPPING


# ---------------------------------------------------------------------------
# adapter.py
# ---------------------------------------------------------------------------


def _bare_adapter():
    from apeiria.webchat.adapter import WebChatAdapter
    from apeiria.webchat.connection import ConnectionManager

    ad = WebChatAdapter.__new__(WebChatAdapter)
    ad.connections = ConnectionManager()
    ad._conn_sessions = {}
    ad._tasks = set()
    return ad


def test_adapter_row_to_wire_outbound_and_inbound() -> None:
    ad = _bare_adapter()
    outbound = SimpleNamespace(
        meta_json={"segments": [{"type": "image", "url": "u"}]},
        role="bot",
        message_id="m1",
        time="t1",
        user_id="webchat",
        content="",
        id=1,
    )
    inbound = SimpleNamespace(
        meta_json=None,
        role="user",
        message_id=None,
        time="t2",
        user_id="u1",
        content="hello",
        id=2,
    )
    w_out = ad._row_to_wire(outbound, "s")
    w_in = ad._row_to_wire(inbound, "s")
    assert w_out["segments"] == [{"type": "image", "url": "u"}]
    assert w_in["id"] == "2"
    assert w_in["segments"] == [{"type": "text", "text": "hello"}]


async def test_adapter_on_frame_bad_json_sends_error() -> None:
    ad = _bare_adapter()
    ws = _FakeWS()
    conn, _ = await ad.connections.add(ws)
    await ad._on_frame(None, conn, "not json{")
    assert ws.sent[-1]["type"] == "error"
    assert ws.sent[-1]["code"] == "bad_frame"


async def test_adapter_on_message_persists_echoes_dispatches(monkeypatch) -> None:
    import asyncio

    import apeiria.webchat.adapter as adapter_mod
    from apeiria.webchat.protocol import InboundMessage

    ensure_calls: list = []
    append_calls: list = []
    dispatched: list = []

    async def fake_ensure(session_id, platform, scene_type, scene_id) -> None:
        ensure_calls.append((session_id, platform, scene_type, scene_id))

    async def fake_append(**kwargs: object) -> None:
        append_calls.append(kwargs)

    async def fake_handle(bot, event) -> None:  # noqa: ARG001
        dispatched.append(event)

    monkeypatch.setattr(adapter_mod, "ensure_session", fake_ensure)
    monkeypatch.setattr(adapter_mod, "append_message", fake_append)
    monkeypatch.setattr(adapter_mod, "handle_event", fake_handle)

    ad = _bare_adapter()
    ws = _FakeWS()
    conn, _ = await ad.connections.add(ws)
    frame = InboundMessage(text="hi", image=None, identity={"user_id": "u1"})

    await ad._on_message(SimpleNamespace(), conn, frame)
    await asyncio.gather(*ad._tasks)

    assert ensure_calls == [("webchat:private:u1", "webchat", "private", "u1")]
    assert append_calls[0]["role"] == "user"
    assert append_calls[0]["meta_json"]["segments"] == [{"type": "text", "text": "hi"}]
    assert ws.sent[-1]["message"]["role"] == "user"
    assert len(dispatched) == 1
    assert dispatched[0].get_session_id() == "webchat:private:u1"
    assert dispatched[0].connection_id == conn


async def test_adapter_on_clear_and_delete(monkeypatch) -> None:
    import apeiria.webchat.adapter as adapter_mod

    deleted_sessions: list = []
    deleted_ids: list = []

    async def fake_del_session(session_id) -> int:
        deleted_sessions.append(session_id)
        return 0

    async def fake_del_message(message_id) -> int:
        deleted_ids.append(message_id)
        return 0

    monkeypatch.setattr(adapter_mod, "delete_session_messages", fake_del_session)
    monkeypatch.setattr(adapter_mod, "delete_message", fake_del_message)

    ad = _bare_adapter()
    ws = _FakeWS()
    conn, _ = await ad.connections.add(ws)
    ad._conn_sessions[conn] = "webchat:private:u1"

    await ad._on_clear(conn)
    assert deleted_sessions == ["webchat:private:u1"]
    assert ws.sent[-1] == {"type": "cleared", "session_id": "webchat:private:u1"}

    await ad._on_delete("mid-9")
    assert deleted_ids == ["mid-9"]
    assert ws.sent[-1] == {"type": "deleted", "message_id": "mid-9"}


async def test_adapter_on_switch_replays_history(monkeypatch) -> None:
    import apeiria.webchat.adapter as adapter_mod
    from apeiria.webchat.protocol import InboundSwitch

    async def fake_load_recent(session_id, limit) -> list:  # noqa: ARG001
        return []

    monkeypatch.setattr(adapter_mod, "load_recent", fake_load_recent)

    ad = _bare_adapter()
    ws = _FakeWS()
    conn, _ = await ad.connections.add(ws)

    await ad._on_switch(conn, InboundSwitch(identity={"user_id": "u1"}))

    assert ad._conn_sessions[conn] == "webchat:private:u1"
    assert ws.sent[-1]["type"] == "history"
    assert ws.sent[-1]["session_id"] == "webchat:private:u1"
