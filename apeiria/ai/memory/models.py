"""Memory domain models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from datetime import datetime

AIMemoryAnchorType = Literal["operator", "scene", "participant", "user", "project"]
AIMemoryScopeHint = Literal["auto", "scene", "participant", "user"]
AIMemoryTargetScope = Literal["scene", "participant", "user"]
AIMemoryLayer = Literal["summary", "long_term", "knowledge", "operator"]
AIMemoryKind = Literal[
    "fact",
    "preference",
    "relationship",
    "note",
    "impression",
]
AIMemoryExtractionAction = Literal["add", "update", "noop"]
AIMemoryLifecycleState = Literal["candidate", "active", "suppressed", "archived"]
AIMemoryBeliefAction = Literal[
    "accept",
    "reject",
    "reinforce",
    "revise",
    "rescope",
    "suppress",
    "activate",
    "archive",
    "supersede",
    "delete",
]
AIMemoryUseMode = Literal["ignore", "silent", "context", "explicit"]
AIObservationLevel = Literal["drop", "observe_light", "observe_deep", "engage"]
AISentimentPolarity = Literal["positive", "neutral", "negative", "playful"]


@dataclass(frozen=True)
class AIMessageSentiment:
    """Sentiment analysis result extracted alongside memory candidates."""

    polarity: AISentimentPolarity
    intensity: float  # 0.0-1.0


@dataclass(frozen=True)
class AIMemoryExtractionCandidate:
    """One structured memory candidate produced by extraction."""

    memory_kind: AIMemoryKind
    content: str
    action: AIMemoryExtractionAction = "add"
    target_memory_id: str | None = None
    scope_hint: AIMemoryScopeHint = "auto"
    confidence: float = 0.7
    salience: float = 0.6


@dataclass(frozen=True)
class AIMemoryGovernanceDecision:
    """Governance result for one extracted memory candidate."""

    action: AIMemoryBeliefAction
    lifecycle_state: AIMemoryLifecycleState | None
    use_mode: AIMemoryUseMode
    target_scope: AIMemoryTargetScope
    reason: str


@dataclass(frozen=True)
class AIMemoryDefinition:
    """Pure memory item representation used by the AI domain."""

    memory_id: str
    anchor_type: AIMemoryAnchorType
    anchor_id: str
    memory_layer: AIMemoryLayer
    memory_kind: AIMemoryKind
    content: str
    is_editable: bool
    lifecycle_state: AIMemoryLifecycleState
    default_use_mode: AIMemoryUseMode
    governance_reason: str | None
    source_message_id: str | None
    salience: float
    confidence: float
    last_recalled_at: datetime | None
    created_at: datetime


@dataclass(frozen=True)
class AIMemoryQuery:
    """Query payload for relevance-ranked memory retrieval."""

    anchor_type: AIMemoryAnchorType
    anchor_id: str
    query_text: str
    limit: int
    memory_layer: AIMemoryLayer | None = None
    memory_kind: AIMemoryKind | None = None


@dataclass(frozen=True)
class AIMemoryRetrievalSelection:
    """One scoped memory selected or excluded for a runtime query."""

    memory: AIMemoryDefinition
    use_mode: AIMemoryUseMode
    scope_rank: int
    exclusion_reason: str | None = None

    @property
    def is_prompt_visible(self) -> bool:
        """Return whether the selection may be projected as prompt memory."""

        return (
            self.use_mode in {"context", "explicit"} and self.exclusion_reason is None
        )


@dataclass(frozen=True)
class AIMemoryRetrievalDiagnostics:
    """Compact retrieval diagnostics safe for traces."""

    selected: tuple[AIMemoryRetrievalSelection, ...]
    excluded: tuple[AIMemoryRetrievalSelection, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return bounded diagnostics for runtime trace metadata."""

        selected = [self._selection_dict(item) for item in self.selected[:8]]
        excluded = [self._selection_dict(item) for item in self.excluded[:8]]
        use_mode_counts: dict[str, int] = {}
        lifecycle_counts: dict[str, int] = {}
        for item in (*self.selected, *self.excluded):
            use_mode_counts[item.use_mode] = use_mode_counts.get(item.use_mode, 0) + 1
            state = item.memory.lifecycle_state
            lifecycle_counts[state] = lifecycle_counts.get(state, 0) + 1
        return {
            "selected": selected,
            "excluded": excluded,
            "use_mode_counts": use_mode_counts,
            "lifecycle_counts": lifecycle_counts,
        }

    @staticmethod
    def _selection_dict(selection: AIMemoryRetrievalSelection) -> dict[str, object]:
        memory = selection.memory
        data: dict[str, object] = {
            "memory_id": memory.memory_id,
            "anchor_type": memory.anchor_type,
            "memory_layer": memory.memory_layer,
            "memory_kind": memory.memory_kind,
            "lifecycle_state": memory.lifecycle_state,
            "use_mode": selection.use_mode,
            "scope_rank": selection.scope_rank,
        }
        if selection.exclusion_reason:
            data["exclusion_reason"] = selection.exclusion_reason
        return data


@dataclass(frozen=True)
class AIMemoryExtractionResult:
    """Combined result of one LLM memory extraction call."""

    candidates: list[AIMemoryExtractionCandidate]
    sentiment: AIMessageSentiment
    self_introduction_name: str | None
