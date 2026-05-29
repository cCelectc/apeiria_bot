"""Provider-neutral turn context contracts for AI session runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.knowledge.models import (
        KnowledgeRetrievalDiagnostics,
        KnowledgeRetrievalItem,
    )
    from apeiria.ai.memory import (
        AIMemoryDefinition,
        AIMemoryRetrievalDiagnostics,
        AIMessageSentiment,
    )
    from apeiria.ai.model import (
        AIModelBindingTarget,
        AIModelMessage,
    )
    from apeiria.ai.prompting import ReplyPersonaPromptBundleLike
    from apeiria.ai.tools import AIToolDefinition, AIToolPolicy
    from apeiria.app.ai.future_tasks.models import AIFutureTaskDefinition
    from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision
    from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
    from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
    from apeiria.conversation.models import ChatContextMessageView, ChatSessionIdentity

from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan

RuntimeMode = Literal["message", "future_task"]
RuntimeSourceMediaKind = Literal["image", "audio", "file"]


@dataclass(frozen=True, slots=True)
class RuntimeSourceMediaPart:
    """Provider-neutral media reference captured from one source message."""

    kind: RuntimeSourceMediaKind
    fallback_text: str | None = None
    url: str | None = None
    asset_id: str | None = None
    file_ref: str | None = None
    path_ref: str | None = None
    base64_data: str | None = None
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    required: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def safe_metadata(self) -> dict[str, object]:
        """Return bounded metadata safe for diagnostics and adapter edges."""

        metadata: dict[str, object] = {}
        for key in ("alt", "width", "height"):
            value = self.metadata.get(key)
            if isinstance(value, (str, int, float, bool)):
                metadata[key] = value
        if self.asset_id:
            metadata["asset_id"] = self.asset_id
        if self.file_ref:
            metadata["file_ref"] = self.file_ref
        if self.path_ref:
            metadata["path_ref"] = self.path_ref
        if self.file_name:
            metadata["file_name"] = self.file_name
        if self.size_bytes is not None:
            metadata["size_bytes"] = self.size_bytes
        return metadata


@dataclass(frozen=True, slots=True)
class RuntimeMediaDiagnostic:
    """Bounded diagnostic for source media that could not be projected."""

    kind: str
    reason: str
    segment_type: str | None = None


@dataclass(frozen=True, slots=True)
class RuntimeTurnSource:
    """Provider-neutral source input for one runtime turn."""

    runtime_mode: RuntimeMode
    message_text: str
    source_message_id: str | None
    user_id: str
    direct_signal: bool = False
    is_private: bool = False
    reply_to_bot: bool = False
    event_dedupe_key: str | None = None
    event_dedupe_claimed: bool = False
    media_parts: tuple[RuntimeSourceMediaPart, ...] = ()
    media_diagnostics: tuple[RuntimeMediaDiagnostic, ...] = ()
    speech_diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class RuntimeTurnInput:
    """Runtime-owned normalized source input for one AI turn."""

    identity: "ChatSessionIdentity"
    source: RuntimeTurnSource
    sender_id: str
    future_task: "AIFutureTaskDefinition | None" = None
    sentiment: "AIMessageSentiment | None" = None
    stream_sink: Any | None = field(default=None, compare=False, repr=False)

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
    profile_card: tuple[str, ...]
    profile_card_source_refs: tuple[str, ...]
    allowed_tools: tuple["AIToolDefinition", ...]
    initiative_bias: float
    memory_diagnostics: "AIMemoryRetrievalDiagnostics | None" = None
    rag_chunks: tuple["KnowledgeRetrievalItem", ...] = ()
    rag_diagnostics: "KnowledgeRetrievalDiagnostics | None" = None


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
    stream_sink: Any | None = field(default=None, compare=False, repr=False)

    @property
    def session_id(self) -> str:
        """Return the canonical AI session id."""

        return self.identity.session_id

    @property
    def runtime_mode(self) -> RuntimeMode:
        """Return the source runtime mode."""

        return self.source.runtime_mode
