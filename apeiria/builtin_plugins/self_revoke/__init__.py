"""Self-revoke plugin for user-triggered bot-message cleanup."""

from __future__ import annotations

from pathlib import Path

from nonebot import get_driver
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_fullmatch, on_message
from nonebot.rule import Rule

from apeiria.i18n import load_locales, t
from apeiria.plugins.metadata.api import (
    CommandDeclaration,
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import SelfRevokeConfig, get_self_revoke_config
from .service import handle_self_revoke_event

load_locales(Path(__file__).parent / "locales")

__plugin_meta__ = PluginMetadata(
    name=t("self_revoke.meta.name"),
    description=t("self_revoke.meta.description"),
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage=t("self_revoke.meta.usage"),
    type="application",
    config=SelfRevokeConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category=t("self_revoke.meta.help_category"),
            introduction=t("self_revoke.meta.help_introduction"),
        ),
        ui=UiExtra(label=t("self_revoke.meta.ui_label"), order=15),
        commands=[
            CommandDeclaration(
                name="撤回",
                description=t("self_revoke.command.revoke"),
                aliases=["revoke"],
                custom_prefix="",
            ),
            CommandDeclaration(
                name="revoke",
                description=t("self_revoke.command.revoke"),
                aliases=["撤回"],
            ),
        ],
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="permission",
                    default="public",
                    help=t("self_revoke.config.permission.help"),
                    type=str,
                    choices=["public", "superuser"],
                    choice_labels={
                        "public": t("self_revoke.config.permission.public"),
                        "superuser": t("self_revoke.config.permission.superuser"),
                    },
                    label=t("self_revoke.config.permission.label"),
                    order=10,
                ),
                RegisterConfig(
                    key="revoke_trigger_message",
                    default=False,
                    help=t("self_revoke.config.revoke_trigger_message.help"),
                    type=bool,
                    label=t("self_revoke.config.revoke_trigger_message.label"),
                    order=20,
                ),
                RegisterConfig(
                    key="feedback",
                    default="silent",
                    help=t("self_revoke.config.feedback.help"),
                    type=str,
                    choices=["silent", "reaction"],
                    choice_labels={
                        "silent": t("self_revoke.config.feedback.silent"),
                        "reaction": t("self_revoke.config.feedback.reaction"),
                    },
                    label=t("self_revoke.config.feedback.label"),
                    order=30,
                ),
            ]
        ),
    ).to_dict(),
)


async def _is_prefixed_self_revoke_message(event: Event) -> bool:
    try:
        text = event.get_plaintext().strip()
    except Exception:  # noqa: BLE001
        return False
    prefix = _strip_command_prefix(text)
    return prefix.lower() in {"撤回", "revoke"} if prefix is not None else False


def _strip_command_prefix(text: str) -> str | None:
    try:
        command_start = getattr(get_driver().config, "command_start", {"/"})
    except Exception:  # noqa: BLE001
        command_start = {"/"}
    if isinstance(command_start, str):
        command_start = {command_start}
    if not isinstance(command_start, (set, list, tuple)):
        command_start = {"/"}
    prefixes = sorted(
        (str(item) for item in command_start if str(item)),
        key=len,
        reverse=True,
    )
    for prefix in prefixes:
        if text.startswith(prefix):
            return text[len(prefix) :].strip()
    return None


_prefixless_revoke = on_fullmatch(
    ("撤回", "revoke"),
    ignorecase=True,
    priority=8,
    block=False,
)
_prefixed_revoke = on_message(
    Rule(_is_prefixed_self_revoke_message),
    priority=8,
    block=False,
)


@_prefixless_revoke.handle()
@_prefixed_revoke.handle()
async def handle_revoke(bot: Bot, event: Event, matcher: Matcher) -> None:
    result = await handle_self_revoke_event(
        bot,
        event,
        config=get_self_revoke_config(),
    )
    if result.should_stop_propagation:
        matcher.stop_propagation()


__all__ = ["_prefixed_revoke", "_prefixless_revoke", "handle_revoke"]
