"""Provider-neutral turn context contracts for AI session runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.memory import AIMemoryDefinition, AIMessageSentiment
    from apeiria.ai.model import AIModelBindingTarget, AIModelMessage
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolPolicy, AIToolSpec
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.context.materials import RuntimeContextInputBundle
    from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
    from apeiria.app.ai.runtime.live import AIRuntimeTurnRequest
    from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
    from apeiria.conversation.models import ChatContextMessageView, ChatSessionIdentity

from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan

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
class RuntimeTurnInput:
    """Runtime-owned normalized source input for one AI turn."""

    identity: "ChatSessionIdentity"
    source: RuntimeTurnSource
    sender_id: str
    future_task: "AIFutureTaskDefinition | None" = None
    sentiment: "AIMessageSentiment | None" = None

    @classmethod
    def from_turn_request(
        cls,
        request: "AIRuntimeTurnRequest",
    ) -> "RuntimeTurnInput":
        """Translate ingress request data into a runtime-owned turn input."""

        identity = request.identity
        return cls(
            identity=identity,
            source=RuntimeTurnSource(
                runtime_mode=request.runtime_mode,
                message_text=request.message_text,
                source_message_id=request.source_message_id,
                user_id=request.user_id,
                direct_signal=request.is_tome,
                is_private=identity.scene_type == "private",
                event_dedupe_key=request.event_dedupe_key,
                event_dedupe_claimed=request.event_dedupe_claimed,
            ),
            sender_id=request.sender_id,
            future_task=request.future_task,
            sentiment=request.sentiment,
        )

    def to_turn_request(self) -> "AIRuntimeTurnRequest":
        """Translate this runtime input back for context-local helpers."""

        from apeiria.app.ai.runtime.live import AIRuntimeTurnRequest

        return AIRuntimeTurnRequest(
            identity=self.identity,
            message_text=self.message_text,
            source_message_id=self.source_message_id,
            user_id=self.user_id,
            sender_id=self.sender_id,
            runtime_mode=self.runtime_mode,
            is_tome=self.is_tome,
            future_task=self.future_task,
            sentiment=self.sentiment,
            event_dedupe_key=self.event_dedupe_key,
            event_dedupe_claimed=self.event_dedupe_claimed,
        )

    @property
    def runtime_mode(self) -> RuntimeMode:
        """Return the source runtime mode."""

        return self.source.runtime_mode

    @property
    def message_text(self) -> str:
        """Return the normalized source message text."""

        return self.source.message_text

    @property
    def source_message_id(self) -> str | None:
        """Return the source message id when available."""

        return self.source.source_message_id

    @property
    def user_id(self) -> str:
        """Return the source user id."""

        return self.source.user_id

    @property
    def is_tome(self) -> bool:
        """Return whether the source directly addressed the bot."""

        return self.source.direct_signal

    @property
    def event_dedupe_key(self) -> str | None:
        """Return the source event dedupe key when available."""

        return self.source.event_dedupe_key

    @property
    def event_dedupe_claimed(self) -> bool:
        """Return whether ingress already claimed the dedupe key."""

        return self.source.event_dedupe_claimed


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
class RuntimeContextMaterials:
    """Runtime-owned prompt and context materials for one reply turn."""

    turns: list["ChatContextMessageView"]
    conversation_summary: str | None
    relationship_target: "AIRelationshipTarget"
    model_target: "AIModelBindingTarget"
    tool_policy: "AIToolPolicy"
    persona: "ReplyPersonaPromptBundleLike | None"
    recalled_memories: list["AIMemoryDefinition"]
    relationship_context: str | None
    person_profile: tuple[str, ...]
    allowed_tools: tuple["AIToolSpec", ...]
    initiative_bias: float

    @classmethod
    def from_context_input_bundle(
        cls,
        inputs: "RuntimeContextInputBundle",
    ) -> "RuntimeContextMaterials":
        """Translate collector output into runtime-owned context materials."""

        return cls(
            turns=inputs.turns,
            conversation_summary=inputs.conversation_summary,
            relationship_target=inputs.relationship_target,
            model_target=inputs.model_target,
            tool_policy=inputs.tool_policy,
            persona=inputs.persona,
            recalled_memories=inputs.recalled_memories,
            relationship_context=inputs.relationship_context,
            person_profile=inputs.person_profile,
            allowed_tools=inputs.allowed_tools,
            initiative_bias=inputs.initiative_bias,
        )


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
