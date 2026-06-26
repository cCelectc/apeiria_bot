from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch

import apeiria.builtin_plugins.contact_approval.workflow as contact_approval_workflow
from apeiria.builtin_plugins.contact_approval.commands import parse_approval_command
from apeiria.builtin_plugins.contact_approval.config import (
    DEFAULT_APPROVAL_PREFIX,
    DEFAULT_TICKET_EXPIRATION_MINUTES,
    ContactApprovalConfig,
    OwnerTarget,
    normalize_contact_approval_config,
    parse_owner_target,
)
from apeiria.builtin_plugins.contact_approval.models import (
    ApprovalTicket,
    IncomingApprovalRequest,
    NotificationRef,
    utcnow_text,
)
from apeiria.builtin_plugins.contact_approval.providers import (
    ContactApprovalActionResult,
    ContactApprovalNotificationResult,
    ContactApprovalProviderRegistry,
    OneBotV11ContactApprovalProvider,
)
from apeiria.builtin_plugins.contact_approval.service import (
    handle_approval_message,
    handle_request_event,
)
from apeiria.builtin_plugins.contact_approval.store import ApprovalTicketStore

EXPECTED_EXPIRATION = 30


def test_contact_approval_config_normalizes_safe_defaults() -> None:
    normalized = normalize_contact_approval_config(
        {
            "owner_targets": [" qq:123456 ", "qq:123456", "qq:0", "bad"],
            "friend_requests_enabled": "false",
            "bot_group_invites_enabled": "yes",
            "group_join_requests_enabled": "off",
            "group_join_gate_mode": "BLACKLIST",
            "group_join_gate_ids": [" 30000 ", "30000", "0", "abc"],
            "suppressed_group_join_action": "reject",
            "ticket_expiration_minutes": str(EXPECTED_EXPIRATION),
            "approval_prefix": " 审核 ",
            "missing_target_reply": "",
        }
    )

    assert normalized["owner_targets"] == (OwnerTarget(scope="qq", target_id="123456"),)
    assert normalized["friend_requests_enabled"] is False
    assert normalized["bot_group_invites_enabled"] is True
    assert normalized["group_join_requests_enabled"] is False
    assert normalized["group_join_gate_mode"] == "blacklist"
    assert normalized["group_join_gate_ids"] == ("30000",)
    assert normalized["suppressed_group_join_action"] == "reject"
    assert normalized["ticket_expiration_minutes"] == EXPECTED_EXPIRATION
    assert normalized["approval_prefix"] == "审核"
    assert normalized["missing_target_reply"]

    fallback = normalize_contact_approval_config(
        {
            "group_join_gate_mode": "unknown",
            "suppressed_group_join_action": "ban",
            "ticket_expiration_minutes": -1,
            "approval_prefix": "",
        }
    )
    assert fallback["group_join_gate_mode"] == "whitelist"
    assert fallback["group_join_gate_ids"] == ()
    assert fallback["suppressed_group_join_action"] == "ignore"
    assert fallback["ticket_expiration_minutes"] == DEFAULT_TICKET_EXPIRATION_MINUTES
    assert fallback["approval_prefix"] == DEFAULT_APPROVAL_PREFIX


def test_owner_target_parsing_is_scoped_to_qq_private_targets() -> None:
    assert parse_owner_target(" qq:123456 ") == OwnerTarget(
        scope="qq",
        target_id="123456",
    )
    assert parse_owner_target("telegram:123456") is None
    assert parse_owner_target("123456") is None
    assert parse_owner_target("qq:0") is None
    assert parse_owner_target("qq:not-number") is None


def test_approval_command_parser_supports_ids_replies_and_safe_bare_actions() -> None:
    approve = parse_approval_command("同意 #f4k9", has_reply_target=False)
    assert approve is not None
    assert approve.action == "approve"
    assert approve.ticket_id == "F4K9"
    assert approve.missing_target is False

    reject = parse_approval_command("拒绝 #G8P2 不认识", has_reply_target=False)
    assert reject is not None
    assert reject.action == "reject"
    assert reject.ticket_id == "G8P2"
    assert reject.reason == "不认识"

    bare_id_reject = parse_approval_command("拒绝 G8P2 不认识", has_reply_target=False)
    assert bare_id_reject is not None
    assert bare_id_reject.ticket_id == "G8P2"
    assert bare_id_reject.reason == "不认识"

    reject_reason_with_number = parse_approval_command(
        "拒绝 不认识1234",
        has_reply_target=True,
    )
    assert reject_reason_with_number is not None
    assert reject_reason_with_number.ticket_id is None
    assert reject_reason_with_number.reason == "不认识1234"

    reply_approve = parse_approval_command("同意", has_reply_target=True)
    assert reply_approve is not None
    assert reply_approve.action == "approve"
    assert reply_approve.ticket_id is None
    assert reply_approve.missing_target is False

    bare_approve = parse_approval_command("同意", has_reply_target=False)
    assert bare_approve is not None
    assert bare_approve.missing_target is True

    custom_list = parse_approval_command(
        "审核",
        has_reply_target=False,
        approval_prefix="审核",
    )
    assert custom_list is not None
    assert custom_list.action == "list"
    assert (
        parse_approval_command(
            "审批",
            has_reply_target=False,
            approval_prefix="审核",
        )
        is None
    )
    assert parse_approval_command("普通消息", has_reply_target=False) is None


def test_ticket_store_persists_updates_notifications_and_terminal_states(
    tmp_path: Path,
) -> None:
    store = _ticket_store(tmp_path, "F4K9", "G8P2")
    request = _incoming(kind="friend_request", flag="friend-flag", comment="hello")

    ticket = store.upsert_pending(request, expires_at=_future_text())
    duplicate = store.upsert_pending(
        request.model_copy(update={"comment": "updated"}),
        expires_at=_future_text(),
    )

    assert ticket.ticket_id == "F4K9"
    assert duplicate.ticket_id == "F4K9"
    assert duplicate.comment == "updated"
    assert len(store.list_all()) == 1

    notified = store.add_notification(
        "f4k9",
        NotificationRef(scene_type="private", scene_id="123456", message_id="msg-1"),
    )
    assert notified is not None
    assert (
        store.get_by_notification(
            scene_type="private",
            scene_id="123456",
            message_id="msg-1",
        )
        == notified
    )
    assert store.list_pending(scene_type="private", scene_id="123456")

    handled, changed = store.mark_terminal(
        "F4K9",
        status="approved",
        handled_by="123456",
    )
    assert changed is True
    assert handled is not None
    assert handled.status == "approved"

    repeated, changed = store.mark_terminal("F4K9", status="rejected")
    assert changed is False
    assert repeated is not None
    assert repeated.status == "approved"


def test_ticket_store_handles_expiration_and_invalid_persistence(
    tmp_path: Path,
) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text("{bad json", encoding="utf-8")
    assert ApprovalTicketStore(invalid_path).list_all() == []

    store = _ticket_store(tmp_path, "F4K9")
    ticket = store.upsert_pending(
        _incoming(kind="group_join_request", group_id="30000", sub_type="add"),
        expires_at=_past_text(),
    )

    expired, changed = store.mark_expired_if_needed(ticket)
    assert changed is True
    assert expired.status == "expired"

    second, changed = store.mark_expired_if_needed(expired)
    assert changed is False
    assert second.status == "expired"


def test_onebot_provider_normalizes_relationship_requests() -> None:
    provider = OneBotV11ContactApprovalProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={
            "get_stranger_info": {"nickname": "Alice"},
            "get_group_info": {"group_name": "测试群"},
        },
    )

    async def scenario() -> None:
        friend = await provider.normalize_request(
            cast("Any", bot),
            cast(
                "Any",
                _FakeEvent(
                    request_type="friend",
                    user_id="20000",
                    flag="friend-flag",
                    comment="加好友",
                ),
            ),
        )
        invite = await provider.normalize_request(
            cast("Any", bot),
            cast(
                "Any",
                _FakeEvent(
                    request_type="group",
                    sub_type="invite",
                    user_id="20000",
                    group_id="30000",
                    flag="invite-flag",
                ),
            ),
        )
        join = await provider.normalize_request(
            cast("Any", bot),
            cast(
                "Any",
                _FakeEvent(
                    request_type="group",
                    sub_type="add",
                    user_id="20001",
                    group_id="30000",
                    flag="join-flag",
                ),
            ),
        )

        assert friend is not None
        assert friend.kind == "friend_request"
        assert friend.nickname == "Alice"
        assert invite is not None
        assert invite.kind == "bot_group_invite"
        assert invite.group_name == "测试群"
        assert join is not None
        assert join.kind == "group_join_request"
        assert join.sub_type == "add"

    assert provider.supports(cast("Any", bot), cast("Any", _FakeEvent()))
    assert not provider.supports(
        cast("Any", _FakeBot(adapter_name="Console")),
        cast("Any", _FakeEvent()),
    )
    asyncio.run(scenario())


def test_onebot_provider_calls_bounded_notification_and_approval_apis() -> None:
    provider = OneBotV11ContactApprovalProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        self_id="10000",
        api_results={
            "send_private_msg": {"message_id": 101},
            "send_group_msg": {"message_id": "202"},
            "get_group_member_info": {"role": "admin"},
        },
    )
    friend = _ticket(kind="friend_request", ticket_id="F4K9", flag="friend-flag")
    group = _ticket(
        kind="group_join_request",
        ticket_id="G8P2",
        flag="group-flag",
        group_id="30000",
        sub_type="add",
    )

    async def scenario() -> None:
        private = await provider.send_owner_notification(
            cast("Any", bot),
            OwnerTarget(scope="qq", target_id="123456"),
            message="card",
        )
        group_notice = await provider.send_group_notification(
            cast("Any", bot),
            group_id="30000",
            message="card",
        )
        role = await provider.is_group_operator(
            cast("Any", bot),
            group_id="30000",
            user_id="20000",
        )
        approved = await provider.approve_ticket(cast("Any", bot), friend)
        rejected = await provider.reject_ticket(
            cast("Any", bot),
            group,
            reason="不认识",
        )

        assert private == ContactApprovalNotificationResult.delivered("101")
        assert group_notice == ContactApprovalNotificationResult.delivered("202")
        assert role == ContactApprovalActionResult.succeeded()
        assert approved.success
        assert rejected.success

    asyncio.run(scenario())

    assert bot.calls == [
        ("send_private_msg", {"user_id": 123456, "message": "card"}),
        ("send_group_msg", {"group_id": 30000, "message": "card"}),
        (
            "get_group_member_info",
            {"group_id": 30000, "user_id": 20000, "no_cache": True},
        ),
        (
            "set_friend_add_request",
            {"flag": "friend-flag", "approve": True, "remark": ""},
        ),
        (
            "set_group_add_request",
            {
                "flag": "group-flag",
                "sub_type": "add",
                "approve": False,
                "reason": "不认识",
            },
        ),
    ]


def test_onebot_provider_returns_bounded_failures() -> None:
    provider = OneBotV11ContactApprovalProvider()
    bot = _FakeBot(
        adapter_name="OneBot V11",
        fail_apis={"send_private_msg", "set_group_add_request"},
    )

    async def scenario() -> None:
        delivery = await provider.send_owner_notification(
            cast("Any", bot),
            OwnerTarget(scope="qq", target_id="123456"),
            message="card",
        )
        action = await provider.approve_ticket(
            cast("Any", bot),
            _ticket(
                kind="group_join_request",
                ticket_id="G8P2",
                flag="group-flag",
                group_id="30000",
                sub_type="add",
            ),
        )

        assert delivery.status == "failed"
        assert delivery.reason == "platform_operation_failed"
        assert action.status == "failed"
        assert action.reason == "platform_operation_failed"

    assert (
        ContactApprovalProviderRegistry((provider,)).resolve(
            cast("Any", _FakeBot(adapter_name="Console")),
            cast("Any", _FakeEvent()),
        )
        is None
    )
    asyncio.run(scenario())


def test_service_routes_friend_and_invite_requests_to_owner_private_cards(
    tmp_path: Path,
) -> None:
    provider = _FakeApprovalProvider(
        requests=(
            _incoming(kind="friend_request", flag="friend-flag", comment="hi"),
            _incoming(
                kind="bot_group_invite",
                flag="invite-flag",
                group_id="30000",
                sub_type="invite",
            ),
        ),
    )
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "F4K9", "G8P2")
    config = _config()

    async def scenario() -> None:
        first = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=config,
            registry=registry,
            store=store,
        )
        second = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=config,
            registry=registry,
            store=store,
        )

        assert first.status == "notified"
        assert second.status == "notified"

    asyncio.run(scenario())

    assert [call[0] for call in provider.notifications] == ["owner", "owner"]
    assert (
        store.get_by_notification(
            scene_type="private",
            scene_id="123456",
            message_id="owner-1",
        )
        is not None
    )
    assert store.get("G8P2") is not None


def test_service_applies_group_join_gate_and_group_notifications(
    tmp_path: Path,
) -> None:
    suppressed_provider = _FakeApprovalProvider(
        requests=(
            _incoming(
                kind="group_join_request",
                flag="join-1",
                group_id="30000",
                sub_type="add",
            ),
        )
    )
    notified_provider = _FakeApprovalProvider(
        requests=(
            _incoming(
                kind="group_join_request",
                flag="join-2",
                group_id="30000",
                sub_type="add",
            ),
        )
    )

    async def scenario() -> None:
        suppressed_store = _ticket_store(tmp_path / "suppressed", "F4K9")
        suppressed = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=_config(),
            registry=ContactApprovalProviderRegistry((suppressed_provider,)),
            store=suppressed_store,
        )
        notified_store = _ticket_store(tmp_path / "notified", "G8P2")
        notified = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=_config(group_join_gate_ids=("30000",)),
            registry=ContactApprovalProviderRegistry((notified_provider,)),
            store=notified_store,
        )

        assert suppressed.status == "suppressed"
        assert suppressed.should_stop_propagation is True
        assert suppressed_store.get("F4K9").status == "suppressed"  # type: ignore[union-attr]
        assert suppressed_provider.notifications == []
        assert notified.status == "notified"
        assert notified.should_stop_propagation is True
        assert notified_provider.notifications[0][0] == "group"
        assert (
            notified_store.get_by_notification(
                scene_type="group",
                scene_id="30000",
                message_id="group-1",
            )
            is not None
        )

    asyncio.run(scenario())


def test_service_can_reject_suppressed_group_join_when_configured(
    tmp_path: Path,
) -> None:
    provider = _FakeApprovalProvider(
        requests=(
            _incoming(
                kind="group_join_request",
                flag="join-1",
                group_id="30000",
                sub_type="add",
            ),
        )
    )

    async def scenario() -> None:
        result = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=_config(
                suppressed_group_join_action="reject",
                suppressed_group_join_reject_reason="暂不开放",
            ),
            registry=ContactApprovalProviderRegistry((provider,)),
            store=_ticket_store(tmp_path, "F4K9"),
        )

        assert result.status == "suppressed"
        assert result.should_stop_propagation is True
        assert provider.rejected == [("F4K9", "暂不开放")]

    asyncio.run(scenario())


def test_service_handles_reply_approval_and_terminal_repeats(tmp_path: Path) -> None:
    provider = _FakeApprovalProvider()
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "F4K9")
    ticket = store.upsert_pending(
        _incoming(kind="friend_request", flag="friend-flag"),
        expires_at=_future_text(),
    )
    store.add_notification(
        ticket.ticket_id,
        NotificationRef(scene_type="private", scene_id="123456", message_id="msg-1"),
    )

    async def scenario() -> None:
        approved = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text="同意",
            reply_message_id="msg-1",
            config=_config(),
            registry=registry,
            store=store,
        )
        repeated = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text="拒绝 #F4K9",
            config=_config(),
            registry=registry,
            store=store,
        )

        assert approved.status == "approved"
        assert approved.should_stop_propagation is True
        assert repeated.status == "already_terminal"
        assert provider.approved == ["F4K9"]
        assert provider.rejected == []

    asyncio.run(scenario())


def test_service_handles_reject_ignore_detail_list_and_safe_failures(
    tmp_path: Path,
) -> None:
    provider = _FakeApprovalProvider()
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "F4K9", "G8P2", "H7N4")
    reject_ticket = store.upsert_pending(
        _incoming(kind="friend_request", flag="friend-flag"),
        expires_at=_future_text(),
    )
    ignore_ticket = store.upsert_pending(
        _incoming(
            kind="bot_group_invite",
            flag="invite-flag",
            group_id="30000",
            sub_type="invite",
        ),
        expires_at=_future_text(),
    )
    detail_ticket = store.upsert_pending(
        _incoming(
            kind="group_join_request",
            flag="join-flag",
            group_id="30000",
            sub_type="add",
            comment="申请入群",
        ),
        expires_at=_future_text(),
    )

    async def scenario() -> None:
        rejected = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text=f"拒绝 #{reject_ticket.ticket_id} 不认识",
            config=_config(),
            registry=registry,
            store=store,
        )
        ignored = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text=f"忽略 #{ignore_ticket.ticket_id}",
            config=_config(),
            registry=registry,
            store=store,
        )
        detail = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456", group_id="30000")),
            message_text=f"详情 #{detail_ticket.ticket_id}",
            config=_config(group_join_gate_ids=("30000",)),
            registry=registry,
            store=store,
        )
        listed = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text="审批",
            config=_config(),
            registry=registry,
            store=store,
        )
        missing = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text="同意",
            config=_config(),
            registry=registry,
            store=store,
        )
        unknown = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text="同意 #ZZZZ",
            config=_config(),
            registry=registry,
            store=store,
        )

        assert rejected.status == "rejected"
        assert provider.rejected == [(reject_ticket.ticket_id, "不认识")]
        assert ignored.status == "local_ignored"
        assert detail.status == "detail"
        assert detail.reply is not None and "申请入群" in detail.reply
        assert listed.status == "listed"
        assert listed.reply is not None and detail_ticket.ticket_id not in listed.reply
        assert missing.status == "missing_target"
        assert unknown.status == "ticket_not_found"

    asyncio.run(scenario())


def test_service_renders_invite_actor_as_inviter(tmp_path: Path) -> None:
    provider = _FakeApprovalProvider(
        requests=(
            _incoming(
                kind="bot_group_invite",
                flag="invite-flag",
                group_id="30000",
                sub_type="invite",
            ),
        ),
    )
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "F4K9")

    async def scenario() -> None:
        notified = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=_config(),
            registry=registry,
            store=store,
        )
        detail = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text="详情 #F4K9",
            config=_config(),
            registry=registry,
            store=store,
        )

        assert notified.status == "notified"
        card = provider.notifications[0][2]
        assert "邀请人：Alice / 20000" in card
        assert detail.reply is not None
        assert "邀请人：Alice / 20000" in detail.reply

    asyncio.run(scenario())


def test_service_ignores_unscoped_commands_outside_approval_scenes(
    tmp_path: Path,
) -> None:
    provider = _FakeApprovalProvider(group_operator_users={"20000"})
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "G8P2")
    ticket = store.upsert_pending(
        _incoming(
            kind="group_join_request",
            flag="join-pending",
            group_id="30000",
            sub_type="add",
        ),
        expires_at=_future_text(),
    )

    async def scenario() -> None:
        unrelated_private_list = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="20000")),
            message_text="审批",
            config=_config(),
            registry=registry,
            store=store,
        )
        ungated_group_list = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="20000", group_id="30000")),
            message_text="审批",
            config=_config(),
            registry=registry,
            store=store,
        )
        explicit_group_action = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="20000", group_id="30000")),
            message_text=f"详情 #{ticket.ticket_id}",
            config=_config(),
            registry=registry,
            store=store,
        )

        assert unrelated_private_list.status == "not_handled"
        assert ungated_group_list.status == "not_handled"
        assert explicit_group_action.status == "detail"

    asyncio.run(scenario())


def test_service_enforces_group_operator_authorization(tmp_path: Path) -> None:
    provider = _FakeApprovalProvider(group_operator_users={"20000"})
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "G8P2", "H7N4")
    allowed_ticket = store.upsert_pending(
        _incoming(
            kind="group_join_request",
            flag="join-allowed",
            group_id="30000",
            sub_type="add",
        ),
        expires_at=_future_text(),
    )
    denied_ticket = store.upsert_pending(
        _incoming(
            kind="group_join_request",
            flag="join-denied",
            group_id="30000",
            sub_type="add",
        ),
        expires_at=_future_text(),
    )

    async def scenario() -> None:
        allowed = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="20000", group_id="30000")),
            message_text=f"同意 #{allowed_ticket.ticket_id}",
            config=_config(group_join_gate_ids=("30000",)),
            registry=registry,
            store=store,
        )
        denied = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="20001", group_id="30000")),
            message_text=f"同意 #{denied_ticket.ticket_id}",
            config=_config(group_join_gate_ids=("30000",)),
            registry=registry,
            store=store,
        )

        assert allowed.status == "approved"
        assert denied.status == "unauthorized"
        assert provider.approved == [allowed_ticket.ticket_id]

    asyncio.run(scenario())


def test_service_keeps_approval_actions_in_their_expected_scenes(
    tmp_path: Path,
) -> None:
    provider = _FakeApprovalProvider(group_operator_users={"20000"})
    registry = ContactApprovalProviderRegistry((provider,))
    store = _ticket_store(tmp_path, "F4K9", "G8P2")
    friend_ticket = store.upsert_pending(
        _incoming(kind="friend_request", flag="friend"),
        expires_at=_future_text(),
    )
    group_ticket = store.upsert_pending(
        _incoming(
            kind="group_join_request",
            flag="join",
            group_id="30000",
            sub_type="add",
        ),
        expires_at=_future_text(),
    )

    async def scenario() -> None:
        owner_group_friend = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456", group_id="30000")),
            message_text=f"同意 #{friend_ticket.ticket_id}",
            config=_config(group_join_gate_ids=("30000",)),
            registry=registry,
            store=store,
        )
        owner_private_group = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text=f"同意 #{group_ticket.ticket_id}",
            config=_config(group_join_gate_ids=("30000",)),
            registry=registry,
            store=store,
        )
        group_operator = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="20000", group_id="30000")),
            message_text=f"详情 #{group_ticket.ticket_id}",
            config=_config(group_join_gate_ids=("30000",)),
            registry=registry,
            store=store,
        )

        assert owner_group_friend.status == "unauthorized"
        assert owner_private_group.status == "unauthorized"
        assert group_operator.status == "detail"
        assert provider.approved == []

    asyncio.run(scenario())


def test_service_handles_expired_and_platform_failed_actions(tmp_path: Path) -> None:
    failing_provider = _FakeApprovalProvider(
        approve_result=ContactApprovalActionResult.failed("platform_operation_failed")
    )
    expired_store = _ticket_store(tmp_path / "expired", "F4K9")
    expired = expired_store.upsert_pending(
        _incoming(kind="friend_request", flag="expired"),
        expires_at=_past_text(),
    )
    failed_store = _ticket_store(tmp_path / "failed", "G8P2")
    failed = failed_store.upsert_pending(
        _incoming(kind="friend_request", flag="failed"),
        expires_at=_future_text(),
    )

    async def scenario() -> None:
        expired_result = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text=f"同意 #{expired.ticket_id}",
            config=_config(),
            registry=ContactApprovalProviderRegistry((failing_provider,)),
            store=expired_store,
        )
        failed_result = await handle_approval_message(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent(user_id="123456")),
            message_text=f"同意 #{failed.ticket_id}",
            config=_config(),
            registry=ContactApprovalProviderRegistry((failing_provider,)),
            store=failed_store,
        )

        assert expired_result.status == "expired"
        assert failed_result.status == "platform_failed"
        assert failing_provider.approved == [failed.ticket_id]

    asyncio.run(scenario())


def test_owner_targets_can_fall_back_to_nonebot_superusers(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        contact_approval_workflow.nonebot,
        "get_driver",
        lambda: SimpleNamespace(
            config=SimpleNamespace(superusers={"onebotv11:123456", "bad"}),
        ),
    )
    provider = _FakeApprovalProvider(
        requests=(_incoming(kind="friend_request", flag="friend-flag"),),
    )

    async def scenario() -> None:
        result = await handle_request_event(
            cast("Any", _FakeBot()),
            cast("Any", _FakeEvent()),
            config=ContactApprovalConfig(),
            registry=ContactApprovalProviderRegistry((provider,)),
            store=_ticket_store(tmp_path, "F4K9"),
        )

        assert result.status == "notified"
        assert provider.notifications[0][1] == "123456"

    asyncio.run(scenario())


def _config(**changes: object) -> ContactApprovalConfig:
    data: dict[str, object] = {
        "owner_targets": (OwnerTarget(scope="qq", target_id="123456"),),
    }
    data.update(changes)
    return ContactApprovalConfig.model_validate(data)


def _ticket_store(tmp_path: Path, *ids: str) -> ApprovalTicketStore:
    pending_ids = list(ids)

    def next_id() -> str:
        if not pending_ids:
            return "ZZ99"
        return pending_ids.pop(0)

    return ApprovalTicketStore(tmp_path / "tickets.json", id_factory=next_id)


def _incoming(  # noqa: PLR0913
    *,
    kind: str,
    flag: str = "flag",
    group_id: str | None = None,
    sub_type: str | None = None,
    user_id: str = "20000",
    comment: str | None = None,
) -> IncomingApprovalRequest:
    return IncomingApprovalRequest(
        kind=cast("Any", kind),
        adapter="onebotv11",
        bot_id="10000",
        user_id=user_id,
        group_id=group_id,
        flag=flag,
        comment=comment,
        sub_type=sub_type,
        nickname="Alice",
        group_name="测试群" if group_id else "",
    )


def _ticket(
    *,
    kind: str,
    ticket_id: str,
    flag: str,
    group_id: str | None = None,
    sub_type: str | None = None,
) -> ApprovalTicket:
    now = utcnow_text()
    return ApprovalTicket(
        ticket_id=ticket_id,
        kind=cast("Any", kind),
        adapter="onebotv11",
        bot_id="10000",
        user_id="20000",
        group_id=group_id,
        flag=flag,
        sub_type=sub_type,
        status="pending",
        created_at=now,
        updated_at=now,
    )


def _future_text() -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(
        timespec="seconds"
    )


def _past_text() -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat(
        timespec="seconds"
    )


class _FakeBot:
    def __init__(
        self,
        *,
        adapter_name: str = "OneBot V11",
        self_id: str = "10000",
        api_results: dict[str, object] | None = None,
        fail_apis: set[str] | None = None,
    ) -> None:
        self.type = adapter_name
        self.self_id = self_id
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.api_results = api_results or {}
        self.fail_apis = fail_apis or set()

    async def call_api(self, api: str, **data: object) -> object:
        self.calls.append((api, data))
        if api in self.fail_apis:
            msg = f"{api} failed"
            raise RuntimeError(msg)
        return self.api_results.get(api, {})


class _Reply:
    def __init__(self, message_id: str | int) -> None:
        self.message_id = message_id


class _FakeEvent:
    def __init__(  # noqa: PLR0913
        self,
        *,
        request_type: str | None = None,
        sub_type: str | None = None,
        user_id: str | int | None = "20000",
        group_id: str | int | None = None,
        flag: str | None = None,
        comment: str | None = None,
        text: str = "",
        reply: object | None = None,
    ) -> None:
        self.request_type = request_type
        self.sub_type = sub_type
        self.user_id = user_id
        self.group_id = group_id
        self.flag = flag
        self.comment = comment
        self.text = text
        self.reply = reply

    def get_user_id(self) -> str:
        return str(self.user_id or "")

    def get_plaintext(self) -> str:
        return self.text


class _FakeApprovalProvider:
    def __init__(
        self,
        *,
        requests: tuple[IncomingApprovalRequest, ...] = (),
        supports: bool = True,
        approve_result: ContactApprovalActionResult | None = None,
        reject_result: ContactApprovalActionResult | None = None,
        group_operator_users: set[str] | None = None,
    ) -> None:
        self._requests = list(requests)
        self._supports = supports
        self._approve_result = approve_result or ContactApprovalActionResult.succeeded()
        self._reject_result = reject_result or ContactApprovalActionResult.succeeded()
        self._group_operator_users = group_operator_users or set()
        self.notifications: list[tuple[str, str, str]] = []
        self.approved: list[str] = []
        self.rejected: list[tuple[str, str]] = []

    def supports(self, bot: object, event: object) -> bool:  # noqa: ARG002
        return self._supports

    async def normalize_request(
        self,
        bot: object,  # noqa: ARG002
        event: object,  # noqa: ARG002
    ) -> IncomingApprovalRequest | None:
        if not self._requests:
            return None
        return self._requests.pop(0)

    async def send_owner_notification(
        self,
        bot: object,  # noqa: ARG002
        target: OwnerTarget,
        *,
        message: str,
    ) -> ContactApprovalNotificationResult:
        message_id = f"owner-{len(self.notifications) + 1}"
        self.notifications.append(("owner", target.target_id, message))
        return ContactApprovalNotificationResult.delivered(message_id)

    async def send_group_notification(
        self,
        bot: object,  # noqa: ARG002
        *,
        group_id: str,
        message: str,
    ) -> ContactApprovalNotificationResult:
        message_id = f"group-{len(self.notifications) + 1}"
        self.notifications.append(("group", group_id, message))
        return ContactApprovalNotificationResult.delivered(message_id)

    async def is_group_operator(
        self,
        bot: object,  # noqa: ARG002
        *,
        group_id: str,  # noqa: ARG002
        user_id: str,
    ) -> ContactApprovalActionResult:
        if user_id in self._group_operator_users:
            return ContactApprovalActionResult.succeeded()
        return ContactApprovalActionResult.failed("operator_not_group_manager")

    async def approve_ticket(
        self,
        bot: object,  # noqa: ARG002
        ticket: ApprovalTicket,
    ) -> ContactApprovalActionResult:
        self.approved.append(ticket.ticket_id)
        return self._approve_result

    async def reject_ticket(
        self,
        bot: object,  # noqa: ARG002
        ticket: ApprovalTicket,
        *,
        reason: str = "",
    ) -> ContactApprovalActionResult:
        self.rejected.append((ticket.ticket_id, reason))
        return self._reject_result
