"""Trigger-reply built-in plugin."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from nonebot import require
from nonebot.adapters import Bot, Event  # noqa: TC002
from nonebot.log import logger
from nonebot.matcher import Matcher  # noqa: TC002
from nonebot.permission import SUPERUSER
from nonebot.plugin import PluginMetadata
from nonebot.plugin.on import on_command, on_message, on_notice
from nonebot.rule import Rule
from nonebot.typing import T_State  # noqa: TC002

from apeiria.plugins.metadata.api import (
    CommandDeclaration,
    ConfigExtra,
    HelpExtra,
    PluginExtraData,
    PluginType,
    RegisterConfig,
    UiExtra,
)

from .config import (
    DEFAULT_DEBUG,
    DEFAULT_ENABLED,
    DEFAULT_PRIORITY,
    DEFAULT_RULES_FILE,
    DEFAULT_STOP_PROPAGATION_ON_MATCH,
    TriggerReplyConfig,
    get_trigger_reply_config,
)
from .loader import default_rule_set_cache, load_trigger_rule_sets
from .models import TriggerEvaluationResult, TriggerInput, TriggerReplyDecision
from .providers import message_input_provider_registry, poke_input_provider_registry
from .service import default_trigger_reply_service

if TYPE_CHECKING:
    from pathlib import Path

require("nonebot_plugin_localstore")
from nonebot_plugin_localstore import get_plugin_config_file

_STATE_MESSAGE_TRIGGER = "_apeiria_trigger_reply_message_trigger"
_STATE_MESSAGE_RESULT = "_apeiria_trigger_reply_message_result"
_STATE_NOTICE_TRIGGER = "_apeiria_trigger_reply_notice_trigger"
_STATE_NOTICE_RESULT = "_apeiria_trigger_reply_notice_result"

__plugin_meta__ = PluginMetadata(
    name="触发回复",
    description="按独立规则文件响应特定消息与戳一戳通知。",
    homepage="https://github.com/Cccc-owo/apeiria_bot",
    usage="在本插件规则文件中配置 entry、matches 与 replies 后自动回复。",
    type="application",
    config=TriggerReplyConfig,
    supported_adapters=None,
    extra=PluginExtraData(
        author="apeiria",
        version="0.1.0",
        plugin_type=PluginType.NORMAL,
        help=HelpExtra(
            category="基础功能",
            introduction="按配置规则响应消息文本和 OneBot v11 戳一戳通知。",
        ),
        ui=UiExtra(label="触发回复", order=19),
        commands=[
            CommandDeclaration(
                name="重载回复",
                description="重新加载触发回复规则文件。",
                aliases=["tr"],
            )
        ],
        config=ConfigExtra(
            fields=[
                RegisterConfig(
                    key="enabled",
                    default=DEFAULT_ENABLED,
                    help="是否启用触发回复。",
                    type=bool,
                    label="启用",
                    order=10,
                ),
                RegisterConfig(
                    key="priority",
                    default=DEFAULT_PRIORITY,
                    help="NoneBot matcher 优先级，数值越小越先执行。",
                    type=int,
                    label="优先级",
                    order=20,
                ),
                RegisterConfig(
                    key="stop_propagation_on_match",
                    default=DEFAULT_STOP_PROPAGATION_ON_MATCH,
                    help="成功发送至少一条回复后是否阻止后续插件处理同一事件。",
                    type=bool,
                    label="命中后阻断事件",
                    order=30,
                ),
                RegisterConfig(
                    key="rules_file",
                    default=[DEFAULT_RULES_FILE],
                    help="localstore 插件配置目录下的规则文件相对路径列表。",
                    type=list,
                    item_type=str,
                    label="规则文件",
                    order=40,
                ),
                RegisterConfig(
                    key="debug",
                    default=DEFAULT_DEBUG,
                    help="启用后记录规则加载与事件跳过原因。",
                    type=bool,
                    label="调试日志",
                    order=50,
                ),
            ]
        ),
        required_plugins=["nonebot_plugin_localstore"],
    ).to_dict(),
)


def trigger_rules_file_path(config: TriggerReplyConfig | None = None) -> Path:
    resolved_config = config or get_trigger_reply_config()
    return get_plugin_config_file(resolved_config.rules_file[0])


def trigger_rules_file_paths(
    config: TriggerReplyConfig | None = None,
) -> tuple[Path, ...]:
    resolved_config = config or get_trigger_reply_config()
    return tuple(
        get_plugin_config_file(rules_file) for rules_file in resolved_config.rules_file
    )


def reload_trigger_rules(
    config: TriggerReplyConfig | None = None,
) -> tuple[int, tuple[str, ...]]:
    ruleset = load_trigger_rule_sets(trigger_rules_file_paths(config))
    default_rule_set_cache.load_count += 1
    if ruleset.status != "invalid":
        default_rule_set_cache.set(ruleset)
        default_trigger_reply_service.cooldown_store.clear()
    if ruleset.status == "invalid":
        logger.warning("Trigger-reply rules invalid: {}", "; ".join(ruleset.errors))
    elif ruleset.status == "missing":
        logger.debug("Trigger-reply rules file missing: {}", ruleset.source_path)
    else:
        logger.info("Trigger-reply loaded {} entries", len(ruleset.entries))
    return len(default_rule_set_cache.ruleset.entries), ruleset.errors


def _ensure_rules_loaded(config: TriggerReplyConfig) -> None:
    if default_rule_set_cache.load_count == 0:
        reload_trigger_rules(config)


async def _is_trigger_message(bot: Bot, event: Event, state: T_State) -> bool:
    config = get_trigger_reply_config()
    if not config.enabled:
        return False
    _ensure_rules_loaded(config)
    trigger = message_input_provider_registry.normalize(bot, event)
    if trigger is None:
        _debug(config, "Trigger-reply skipped message: unsupported input")
        return False
    result = default_trigger_reply_service.evaluate(
        trigger,
        ruleset=default_rule_set_cache.ruleset,
    )
    if not result.should_reply:
        _debug(
            config,
            "Trigger-reply skipped message from user {}: no matched entry",
            trigger.user_id,
        )
        return False
    _debug(
        config,
        "Trigger-reply matched message entries: {}",
        [decision.entry.id for decision in result.decisions],
    )
    default_trigger_reply_service.reserve_cooldowns(result)
    state[_STATE_MESSAGE_TRIGGER] = trigger
    state[_STATE_MESSAGE_RESULT] = result
    return True


async def _is_trigger_notice(bot: Bot, event: Event, state: T_State) -> bool:
    config = get_trigger_reply_config()
    if not config.enabled:
        return False
    _ensure_rules_loaded(config)
    provider = poke_input_provider_registry.resolve(bot, event)
    if provider is None:
        _debug(config, "Trigger-reply skipped notice: unsupported provider")
        return False
    trigger = provider.normalize(bot, event)
    if trigger is None:
        _debug(config, "Trigger-reply skipped notice: unsupported input")
        return False
    result = default_trigger_reply_service.evaluate(
        trigger,
        ruleset=default_rule_set_cache.ruleset,
    )
    if not result.should_reply:
        _debug(config, "Trigger-reply skipped notice: no matched entry")
        return False
    _debug(
        config,
        "Trigger-reply matched notice entries: {}",
        [decision.entry.id for decision in result.decisions],
    )
    default_trigger_reply_service.reserve_cooldowns(result)
    state[_STATE_NOTICE_TRIGGER] = trigger
    state[_STATE_NOTICE_RESULT] = result
    return True


_message = on_message(
    Rule(_is_trigger_message),
    priority=get_trigger_reply_config().priority,
    block=False,
)
_notice = on_notice(
    Rule(_is_trigger_notice),
    priority=get_trigger_reply_config().priority,
    block=False,
)
_reload = on_command(
    "重载回复",
    aliases={"tr"},
    permission=SUPERUSER,
    block=True,
)


@_message.handle()
async def handle_trigger_message(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    state: T_State,
) -> None:
    config = get_trigger_reply_config()
    try:
        result = _message_result_from_state(state)
        if result is None:
            result = _evaluate_message(bot, event, config)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Trigger-reply message evaluation failed: {}", exc)
        return
    sent_decisions: tuple[TriggerReplyDecision, ...] = ()
    try:
        sent_decisions = await _send_trigger_message_decisions(matcher, result)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Trigger-reply message handler failed: {}", exc)
    finally:
        _release_unsent_cooldowns(result, sent_decisions)
    if sent_decisions and config.stop_propagation_on_match:
        matcher.stop_propagation()


async def _send_trigger_message_decisions(
    matcher: Matcher,
    result: TriggerEvaluationResult,
) -> tuple[TriggerReplyDecision, ...]:
    sent: list[TriggerReplyDecision] = []
    for decision in result.decisions:
        try:
            await matcher.send(cast("Any", decision.reply))
        except Exception as exc:  # noqa: BLE001
            logger.debug("Trigger-reply message send failed: {}", exc)
            default_trigger_reply_service.release_cooldowns((decision,))
            continue
        default_trigger_reply_service.commit_cooldowns((decision,))
        sent.append(decision)
    return tuple(sent)


@_notice.handle()
async def handle_trigger_notice(
    bot: Bot,
    event: Event,
    matcher: Matcher,
    state: T_State,
) -> None:
    config = get_trigger_reply_config()
    result: TriggerEvaluationResult | None = None
    sent_decisions: tuple[TriggerReplyDecision, ...] = ()
    try:
        provider = poke_input_provider_registry.resolve(bot, event)
        if provider is None:
            return
        trigger = _notice_trigger_from_state(state)
        if trigger is None:
            trigger = provider.normalize(bot, event)
        if trigger is None:
            return
        result = _notice_result_from_state(state)
        if result is None:
            _ensure_rules_loaded(config)
            result = default_trigger_reply_service.evaluate(
                trigger,
                ruleset=default_rule_set_cache.ruleset,
            )
        sent_decisions = await _send_trigger_notice_decisions(
            bot,
            provider,
            trigger,
            result,
        )
        if sent_decisions and config.stop_propagation_on_match:
            matcher.stop_propagation()
    except Exception as exc:  # noqa: BLE001
        logger.debug("Trigger-reply notice handler failed: {}", exc)
    finally:
        if result is not None:
            _release_unsent_cooldowns(result, sent_decisions)


async def _send_trigger_notice_decisions(
    bot: Bot,
    provider: Any,
    trigger: TriggerInput,
    result: TriggerEvaluationResult,
) -> tuple[TriggerReplyDecision, ...]:
    sent: list[TriggerReplyDecision] = []
    for decision in result.decisions:
        try:
            delivery = await provider.send_reply(
                bot,
                trigger,
                message=decision.reply,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("Trigger-reply notice send failed: {}", exc)
            default_trigger_reply_service.release_cooldowns((decision,))
            continue
        if delivery.success:
            default_trigger_reply_service.commit_cooldowns((decision,))
            sent.append(decision)
        else:
            default_trigger_reply_service.release_cooldowns((decision,))
    return tuple(sent)


@_reload.handle()
async def handle_trigger_reply_reload() -> None:
    config = get_trigger_reply_config()
    count, errors = reload_trigger_rules(config)
    if errors:
        await _reload.finish(
            f"触发回复规则已重载：{count} 条可用，{len(errors)} 个错误。"
        )
    await _reload.finish(f"触发回复规则已重载：{count} 条可用。")


def _evaluate_message(
    bot: Bot,
    event: Event,
    config: TriggerReplyConfig,
) -> TriggerEvaluationResult:
    trigger = message_input_provider_registry.normalize(bot, event)
    if trigger is None:
        return TriggerEvaluationResult()
    _ensure_rules_loaded(config)
    return default_trigger_reply_service.evaluate(
        trigger,
        ruleset=default_rule_set_cache.ruleset,
    )


def _message_result_from_state(state: T_State) -> TriggerEvaluationResult | None:
    value = state.get(_STATE_MESSAGE_RESULT)
    return value if isinstance(value, TriggerEvaluationResult) else None


def _notice_result_from_state(state: T_State) -> TriggerEvaluationResult | None:
    value = state.get(_STATE_NOTICE_RESULT)
    return value if isinstance(value, TriggerEvaluationResult) else None


def _notice_trigger_from_state(state: T_State) -> TriggerInput | None:
    value = state.get(_STATE_NOTICE_TRIGGER)
    return value if isinstance(value, TriggerInput) else None


def _release_unsent_cooldowns(
    result: TriggerEvaluationResult,
    sent_decisions: tuple[TriggerReplyDecision, ...],
) -> None:
    sent_ids = {id(decision) for decision in sent_decisions}
    default_trigger_reply_service.release_cooldowns(
        decision for decision in result.decisions if id(decision) not in sent_ids
    )


def _debug(config: TriggerReplyConfig, message: str, *args: object) -> None:
    if config.debug:
        logger.debug(message, *args)


__all__ = [
    "_message",
    "_notice",
    "_reload",
    "handle_trigger_message",
    "handle_trigger_notice",
    "handle_trigger_reply_reload",
    "reload_trigger_rules",
    "trigger_rules_file_path",
    "trigger_rules_file_paths",
]
