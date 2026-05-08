from __future__ import annotations

import re
from pathlib import Path

from apeiria.app.chat.protocol import (
    CLIENT_FRAME_TYPES,
    SERVER_FRAME_TYPES,
    AuthHelloPayload,
    AuthOkPayload,
    CapabilitiesResponsePayload,
    ChatCapabilities,
    ChatEnvelope,
    ChatSessionState,
    ErrorPayload,
    MessageAckPayload,
    MessageReceivePayload,
    MessageSendPayload,
    PartialReplyCompletePayload,
    PartialReplyDeltaPayload,
    PartialReplyFailedPayload,
    PartialReplyStartPayload,
    SessionCreatePayload,
    SessionDeletePayload,
    SessionListItem,
    SessionSelectPayload,
    SessionSnapshotPayload,
    SystemMessagePayload,
    WebUIPrincipal,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CHAT_API = REPO_ROOT / "web" / "src" / "api" / "chat.ts"
CHAT_VIEW = REPO_ROOT / "web" / "src" / "views" / "ChatView.vue"
CHAT_TYPES = REPO_ROOT / "web" / "src" / "types" / "chat.ts"


def test_browser_chat_client_exposes_send_result_for_local_failures() -> None:
    source = CHAT_API.read_text(encoding="utf-8")

    assert "export interface ChatSendResult" in source
    assert "readyState !== WebSocket.OPEN" in source
    assert "sent: false" in source


def test_webchat_frame_names_are_declared_in_browser_sources() -> None:
    client_source = CHAT_API.read_text(encoding="utf-8")
    view_source = CHAT_VIEW.read_text(encoding="utf-8")

    missing_client_frames = [
        frame for frame in CLIENT_FRAME_TYPES if f"'{frame}'" not in client_source
    ]
    missing_server_frames = [
        frame
        for frame in SERVER_FRAME_TYPES
        if f"'{frame}'" not in view_source and f"'{frame}'" not in client_source
    ]

    assert not missing_client_frames
    assert not missing_server_frames


def test_webchat_payload_fields_match_browser_types() -> None:
    type_source = CHAT_TYPES.read_text(encoding="utf-8")
    payload_types = (
        AuthHelloPayload,
        AuthOkPayload,
        CapabilitiesResponsePayload,
        ChatCapabilities,
        ChatEnvelope,
        ChatSessionState,
        ErrorPayload,
        MessageAckPayload,
        MessageReceivePayload,
        MessageSendPayload,
        PartialReplyCompletePayload,
        PartialReplyDeltaPayload,
        PartialReplyFailedPayload,
        PartialReplyStartPayload,
        SessionCreatePayload,
        SessionDeletePayload,
        SessionListItem,
        SessionSelectPayload,
        SessionSnapshotPayload,
        SystemMessagePayload,
        WebUIPrincipal,
    )

    mismatches = []
    for payload_type in payload_types:
        python_fields = set(payload_type.model_fields)
        browser_fields = _typescript_interface_fields(
            type_source, payload_type.__name__
        )
        if python_fields != browser_fields:
            mismatches.append(
                f"{payload_type.__name__}: python={sorted(python_fields)} "
                f"browser={sorted(browser_fields)}"
            )

    assert not mismatches, "\n".join(mismatches)


def _typescript_interface_fields(source: str, interface_name: str) -> set[str]:
    pattern = re.compile(
        rf"export interface {re.escape(interface_name)}(?:<[^>]+>)? "
        r"\{(?P<body>.*?)\n\}",
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match is not None, f"missing TypeScript interface: {interface_name}"
    fields: set[str] = set()
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("//"):
            continue
        field_match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\??:", line)
        if field_match is not None:
            fields.add(field_match.group(1))
    return fields
