"""Provider-neutral turn context contracts for AI session runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.model import AIModelBindingTarget, AIModelMessage
    from apeiria.ai.tools import AIToolPolicy
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.session_runtime.strategy import RuntimeHardRuleDecision
    from apeiria.app.ai.session_runtime.tools import ToolExposurePlan
    from apeiria.conversation.models import ChatSessionIdentity

from .tools import ToolExposurePlan

RuntimeMode = Literal["message", "future_task"]


@dataclass(frozen=True, slots=True)
class RuntimeTurnSource:
    """Provider-neutral source input for one runtime turn."""

    runtime_mode: RuntimeMode
    message_text: str
    source_message_id: str | None
    user_id: str
    direct_signal: bool = False
    is_private: bool = False
    event_dedupe_key: str | None = None
    event_dedupe_claimed: bool = False


@dataclass(frozen=True, slots=True)
class DeliveryTarget:
    """Provider-neutral reply delivery hints for one turn."""

    session_id: str
    reply_to_message_id: str | None = None
    delivery_channel: str | None = None


@dataclass(frozen=True, slots=True)
class MergeMetadata:
    """Metadata for same-session input folded into one turn."""

    merged_message_ids: tuple[str, ...] = ()
    merged_message_count: int = 0
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class TurnContext:
    """Frozen provider-neutral snapshot used by runner execution."""

    trace_id: str
    identity: "ChatSessionIdentity"
    source: RuntimeTurnSource
    delivery_target: DeliveryTarget
    current_time: "datetime"
    model_target: "AIModelBindingTarget"
    tool_policy: "AIToolPolicy"
    tool_exposure_plan: "ToolExposurePlan" = field(default_factory=ToolExposurePlan)
    prompt_messages: tuple["AIModelMessage", ...] = ()
    prompt_diagnostics: dict[str, object] = field(default_factory=dict)
    merge: MergeMetadata = MergeMetadata()
    hard_rule_decision: "RuntimeHardRuleDecision | None" = None
    social_decision: "ReplyStrategyDecision | None" = None

    @property
    def session_id(self) -> str:
        """Return the canonical AI session id."""

        return self.identity.session_id

    @property
    def runtime_mode(self) -> RuntimeMode:
        """Return the source runtime mode."""

        return self.source.runtime_mode
