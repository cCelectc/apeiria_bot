from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from apeiria.conversation.identity import build_participant_subject_id
from apeiria.conversation.models import ChatSessionIdentity
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


def test_lifecycle_states_are_excluded_from_runtime_context(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import AIMemoryCreateInput, ai_memory_service
    from apeiria.app.ai.runtime.context.memories import (
        retrieve_memory_diagnostics_for_context,
    )

    identity = _private_identity()

    async def scenario() -> None:
        for lifecycle_state in ("active", "candidate", "suppressed", "archived"):
            await ai_memory_service.create_memory(
                AIMemoryCreateInput(
                    anchor_type="scene",
                    anchor_id=identity.session_id,
                    memory_layer="long_term",
                    memory_kind="note",
                    content=f"{lifecycle_state} project preference",
                    lifecycle_state=lifecycle_state,
                    default_use_mode=(
                        "context" if lifecycle_state == "active" else "ignore"
                    ),
                    governance_reason=f"test {lifecycle_state}",
                    salience=0.8,
                    confidence=0.9,
                )
            )

        diagnostics = await retrieve_memory_diagnostics_for_context(
            identity=identity,
            user_id="user-1",
            query_text="project preference",
        )

        assert [item.memory.lifecycle_state for item in diagnostics.selected] == [
            "active"
        ]
        assert {
            item.memory.lifecycle_state
            for item in diagnostics.excluded
            if item.memory.memory_layer == "long_term"
        } == {"candidate", "suppressed", "archived"}
        assert diagnostics.as_dict()["selected"][0]["memory_id"]
        assert "content" not in diagnostics.as_dict()["selected"][0]

    asyncio.run(scenario())


def test_group_participant_memory_does_not_leak_between_users(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import AIMemoryCreateInput, ai_memory_service
    from apeiria.app.ai.runtime.context.memories import (
        retrieve_memory_diagnostics_for_context,
    )

    identity = _group_identity()
    user_a_subject = build_participant_subject_id(
        scene_type="group",
        scene_id="group-1",
        user_id="user-a",
    )
    user_b_subject = build_participant_subject_id(
        scene_type="group",
        scene_id="group-1",
        user_id="user-b",
    )

    async def scenario() -> None:
        await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="participant",
                anchor_id=user_a_subject,
                memory_layer="long_term",
                memory_kind="preference",
                content="likes python examples",
                salience=0.8,
                confidence=0.9,
            )
        )
        await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="participant",
                anchor_id=user_b_subject,
                memory_layer="long_term",
                memory_kind="preference",
                content="likes rust examples",
                salience=0.8,
                confidence=0.9,
            )
        )

        diagnostics = await retrieve_memory_diagnostics_for_context(
            identity=identity,
            user_id="user-a",
            query_text="examples",
        )

        assert [item.memory.anchor_id for item in diagnostics.selected] == [
            user_a_subject
        ]
        assert [item.memory.content for item in diagnostics.selected] == [
            "likes python examples"
        ]

    asyncio.run(scenario())


def test_subjective_beliefs_default_to_silent_use(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import (
        AIMemoryExtractionCandidate,
        AIMemoryQuery,
        ai_memory_service,
    )

    async def scenario() -> None:
        created = await ai_memory_service.remember_candidates(
            anchor_type="user",
            anchor_id="user-1",
            source_message_id=None,
            candidates=[
                AIMemoryExtractionCandidate(
                    memory_kind="impression",
                    content="prefers careful disagreement",
                    confidence=0.9,
                    salience=0.8,
                )
            ],
        )
        assert created[0].lifecycle_state == "active"
        assert created[0].default_use_mode == "silent"

        diagnostics = await ai_memory_service.retrieve_memory_selections(
            AIMemoryQuery(
                anchor_type="user",
                anchor_id="user-1",
                query_text="careful disagreement",
                limit=5,
                memory_layer="long_term",
            )
        )

        assert diagnostics.selected[0].use_mode == "silent"
        assert diagnostics.selected[0].is_prompt_visible is False

    asyncio.run(scenario())


def test_memory_retrieval_uses_sparse_after_policy_filtering(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import AIMemoryCreateInput, AIMemoryQuery, ai_memory_service
    from apeiria.ai.memory import service as memory_service_module
    from apeiria.ai.retrieval import service as retrieval_service_module

    async def select_default_model(*, capability_type: str) -> object | None:
        del capability_type
        return None

    monkeypatch.setattr(
        retrieval_service_module.ai_model_capability_selection_service,
        "select_default_model",
        select_default_model,
    )
    assert not hasattr(memory_service_module, "rank_memory_items")

    async def scenario() -> None:
        selected = await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="preference",
                content="喜欢原神多人联机",
                salience=0.8,
                confidence=0.9,
            )
        )
        await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="preference",
                content="喜欢烤面包",
                default_use_mode="ignore",
                salience=0.8,
                confidence=0.9,
            )
        )
        await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="preference",
                content="候选原神资料",
                lifecycle_state="candidate",
                default_use_mode="ignore",
                salience=0.8,
                confidence=0.9,
            )
        )

        rows = await ai_memory_service.retrieve_memories(
            AIMemoryQuery(
                anchor_type="user",
                anchor_id="user-1",
                query_text="原神联机",
                limit=5,
                memory_layer="long_term",
            )
        )
        diagnostics = await ai_memory_service.retrieve_memory_selections(
            AIMemoryQuery(
                anchor_type="user",
                anchor_id="user-1",
                query_text="原神联机",
                limit=5,
                memory_layer="long_term",
            )
        )

        assert [item.memory_id for item in rows] == [selected.memory_id]
        assert [item.memory.memory_id for item in diagnostics.selected] == [
            selected.memory_id
        ]
        assert {
            item.exclusion_reason
            for item in diagnostics.excluded
            if item.exclusion_reason
        } == {"lifecycle_state:candidate"}

    asyncio.run(scenario())


def test_group_extracted_memories_are_written_to_one_scope(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import (
        AIMemoryExtractionCandidate,
        AIMemoryExtractionResult,
        AIMessageSentiment,
        ai_memory_service,
    )
    from apeiria.app.ai.runtime.context import memories as runtime_memories

    identity = _group_identity()
    participant_id = build_participant_subject_id(
        scene_type="group",
        scene_id="group-1",
        user_id="user-a",
    )

    async def fake_extract_memory_from_message(
        *,
        message_text: str,
        existing_memories: tuple[object, ...],
    ) -> AIMemoryExtractionResult:
        del message_text, existing_memories
        return AIMemoryExtractionResult(
            candidates=[
                AIMemoryExtractionCandidate(
                    memory_kind="preference",
                    content="prefers examples in python",
                    confidence=0.9,
                    salience=0.8,
                ),
                AIMemoryExtractionCandidate(
                    memory_kind="note",
                    content="the group is discussing plugin architecture",
                    confidence=0.9,
                    salience=0.8,
                ),
            ],
            sentiment=AIMessageSentiment(polarity="neutral", intensity=0.0),
            self_introduction_name=None,
        )

    async def noop_consolidate_anchor_summary(
        *,
        anchor_type: object,
        anchor_id: str,
    ) -> object:
        del anchor_type, anchor_id
        return None

    monkeypatch.setattr(
        runtime_memories,
        "extract_memory_from_message",
        fake_extract_memory_from_message,
    )
    monkeypatch.setattr(
        ai_memory_service,
        "consolidate_anchor_summary",
        noop_consolidate_anchor_summary,
    )

    async def scenario() -> None:
        await runtime_memories.store_extracted_memories(
            identity=identity,
            user_id="user-a",
            message_text="remember these",
            source_message_id=None,
        )

        scene_memories = await ai_memory_service.list_memories(
            anchor_type="scene",
            anchor_id=identity.session_id,
            memory_layer="long_term",
        )
        participant_memories = await ai_memory_service.list_memories(
            anchor_type="participant",
            anchor_id=participant_id,
            memory_layer="long_term",
        )
        user_memories = await ai_memory_service.list_memories(
            anchor_type="user",
            anchor_id="user-a",
            memory_layer="long_term",
        )

        assert [memory.content for memory in scene_memories] == [
            "the group is discussing plugin architecture"
        ]
        assert [memory.content for memory in participant_memories] == [
            "prefers examples in python"
        ]
        assert user_memories == []

    asyncio.run(scenario())


def test_explicit_scope_hint_overrides_default_write_scope() -> None:
    from apeiria.ai.memory import AIMemoryExtractionCandidate
    from apeiria.app.ai.runtime.context.memories import (
        build_memory_write_anchors,
        select_memory_write_anchor,
    )

    identity = _group_identity()
    anchor = select_memory_write_anchor(
        identity=identity,
        candidate=AIMemoryExtractionCandidate(
            memory_kind="preference",
            content="this preference applies to the whole group",
            scope_hint="scene",
            confidence=0.9,
            salience=0.8,
        ),
        write_anchors=build_memory_write_anchors(identity, "user-a"),
    )

    assert anchor is not None
    assert anchor.anchor_type == "scene"
    assert anchor.anchor_id == identity.session_id


def test_extraction_project_scope_hint_falls_back_to_auto() -> None:
    from apeiria.ai.memory.extraction import parse_memory_extraction_response

    result = parse_memory_extraction_response(
        """
        {
          "memories": [{
            "memory_kind": "preference",
            "content": "prefers project-level summaries",
            "scope_hint": "project",
            "confidence": 0.9,
            "salience": 0.8
          }],
          "sentiment": {"polarity": "neutral", "intensity": 0.0},
          "self_introduction_name": null
        }
        """
    )

    assert result.candidates[0].scope_hint == "auto"


def test_governance_assigns_scope_for_group_candidate() -> None:
    from apeiria.ai.memory import AIMemoryExtractionCandidate
    from apeiria.ai.memory.governance import govern_extracted_memory

    decision = govern_extracted_memory(
        AIMemoryExtractionCandidate(
            memory_kind="preference",
            content="prefers examples in python",
            confidence=0.9,
            salience=0.8,
        ),
        scene_type="group",
    )

    assert decision.target_scope == "participant"


def test_remember_candidates_rejects_scope_mismatch(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import AIMemoryExtractionCandidate, ai_memory_service

    async def scenario() -> None:
        created = await ai_memory_service.remember_candidates(
            anchor_type="scene",
            anchor_id="scene-1",
            source_message_id=None,
            scene_type="group",
            candidates=[
                AIMemoryExtractionCandidate(
                    memory_kind="preference",
                    content="prefers examples in python",
                    confidence=0.9,
                    salience=0.8,
                )
            ],
        )

        memories = await ai_memory_service.list_memories(
            anchor_type="scene",
            anchor_id="scene-1",
            lifecycle_states=(),
        )

        assert created == []
        assert memories == []
        assert _belief_actions() == ["reject"]

    asyncio.run(scenario())


def test_context_memory_retrieval_does_not_mutate_beliefs(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import AIMemoryCreateInput, ai_memory_service
    from apeiria.app.ai.runtime.context.memories import (
        retrieve_memory_diagnostics_for_context,
    )

    identity = _private_identity()

    async def scenario() -> None:
        memory = await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="scene",
                anchor_id=identity.session_id,
                memory_layer="long_term",
                memory_kind="preference",
                content="likes direct answers",
                salience=0.8,
                confidence=0.9,
            )
        )
        before_actions = _belief_action_count()

        diagnostics = await retrieve_memory_diagnostics_for_context(
            identity=identity,
            user_id="user-1",
            query_text="direct answers",
        )
        after = await ai_memory_service.get_memory(memory_id=memory.memory_id)

        assert [item.memory.memory_id for item in diagnostics.selected] == [
            memory.memory_id
        ]
        assert _belief_action_count() == before_actions
        assert after is not None
        assert after.last_recalled_at is None

    asyncio.run(scenario())


def test_memory_revision_and_deletion_record_belief_actions(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import (
        AIMemoryCreateInput,
        AIMemoryUpdateInput,
        ai_memory_service,
    )

    async def scenario() -> None:
        memory = await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="note",
                content="prefers short examples",
            )
        )
        await ai_memory_service.update_memory_content(
            memory_id=memory.memory_id,
            update_input=AIMemoryUpdateInput(
                content="prefers concise examples",
                salience=0.7,
                confidence=0.8,
                source_message_id=None,
            ),
        )
        await ai_memory_service.delete_memory(memory_id=memory.memory_id)

        assert _belief_actions() == ["accept", "revise", "delete"]

    asyncio.run(scenario())


def test_bulk_lifecycle_records_actions_only_for_existing_memories(
    tmp_path: Path,
    monkeypatch: "MonkeyPatch",
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.memory import AIMemoryCreateInput, ai_memory_service

    async def scenario() -> None:
        memory = await ai_memory_service.create_memory(
            AIMemoryCreateInput(
                anchor_type="user",
                anchor_id="user-1",
                memory_layer="long_term",
                memory_kind="note",
                content="existing memory",
            )
        )

        count = await ai_memory_service.bulk_set_memory_state(
            memory_ids=["missing-memory", memory.memory_id],
            lifecycle_state="suppressed",
            governance_reason="test bulk suppression",
        )

        assert count == 1
        assert _belief_actions() == ["accept", "suppress"]

    asyncio.run(scenario())


def test_observation_classification_keeps_ambient_candidate_light() -> None:
    from apeiria.app.ai.runtime.observation import classify_observation_level
    from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision

    assert (
        classify_observation_level(
            RuntimeHardRuleDecision(
                action="continue",
                reason_codes=("direct_signal",),
                reason_text="direct",
                evidence={},
                should_observe=True,
                should_reply=True,
            )
        )
        == "engage"
    )
    assert (
        classify_observation_level(
            RuntimeHardRuleDecision(
                action="continue",
                reason_codes=("ambient_candidate",),
                reason_text="ambient",
                evidence={},
                should_observe=True,
                should_reply=True,
            )
        )
        == "observe_light"
    )
    assert (
        classify_observation_level(
            RuntimeHardRuleDecision(
                action="observe",
                reason_codes=("ambient_cooldown",),
                reason_text="cooldown",
                evidence={},
                should_observe=True,
                should_reply=False,
            )
        )
        == "observe_light"
    )
    assert (
        classify_observation_level(
            RuntimeHardRuleDecision(
                action="observe",
                reason_codes=("ambient_cooldown",),
                reason_text="deep observation requested",
                evidence={"observe_deep": True},
                should_observe=True,
                should_reply=False,
            )
        )
        == "observe_deep"
    )


def test_runtime_ambient_candidate_does_not_run_deep_observation() -> None:
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
    from apeiria.app.ai.runtime.session.context import (
        RuntimeTurnInput,
        RuntimeTurnSource,
    )

    calls: list[str] = []
    identity = _group_identity()

    async def scenario() -> None:
        engine = AISessionTurnEngine(
            policy_stage=_PolicyStub(
                action="continue",
                reason_code="ambient_candidate",
                should_reply=True,
                should_observe=True,
            ),
            observation_stage=_ObservationStub(calls),
            context_stage=_ContextStub(),
            planning_stage=_PlanningStub(return_plan=False),
            trace_stage=_TraceStub(),
        )

        result = await engine.run_reply_turn(
            trace_id="trace-1",
            trace=object(),
            turn=RuntimeTurnInput(
                identity=identity,
                source=RuntimeTurnSource(
                    runtime_mode="message",
                    message_text="ambient group note",
                    source_message_id="message-1",
                    user_id="user-1",
                ),
                sender_id="bot-1",
            ),
            wake_context=WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="ambient group note",
                is_tome=False,
                is_private=False,
                is_future_task=False,
            ),
            current_time=datetime.now(timezone.utc),
            session_runtime=None,
        )

        assert result is None
        assert calls == ["observation_side_effects"]

    asyncio.run(scenario())


def test_runtime_direct_engagement_runs_deep_observation_before_side_effects() -> None:
    from apeiria.app.ai.reply_strategy.models import WakeContext
    from apeiria.app.ai.runtime.orchestrator import AISessionTurnEngine
    from apeiria.app.ai.runtime.session.context import (
        RuntimeTurnInput,
        RuntimeTurnSource,
    )

    calls: list[str] = []
    identity = _private_identity()

    async def scenario() -> None:
        engine = AISessionTurnEngine(
            policy_stage=_PolicyStub(
                action="continue",
                reason_code="direct_signal",
                should_reply=True,
                should_observe=True,
                evidence={"direct_signal": True},
            ),
            observation_stage=_ObservationStub(calls),
            context_stage=_ContextStub(),
            planning_stage=_PlanningStub(return_plan=False),
            trace_stage=_TraceStub(),
        )

        result = await engine.run_reply_turn(
            trace_id="trace-1",
            trace=object(),
            turn=RuntimeTurnInput(
                identity=identity,
                source=RuntimeTurnSource(
                    runtime_mode="message",
                    message_text="bot, remember this",
                    source_message_id="message-1",
                    user_id="user-1",
                    direct_signal=True,
                    is_private=True,
                ),
                sender_id="bot-1",
            ),
            wake_context=WakeContext(
                bot_self_id="bot-1",
                user_id="user-1",
                message_text="bot, remember this",
                is_tome=True,
                is_private=True,
                is_future_task=False,
            ),
            current_time=datetime.now(timezone.utc),
            session_runtime=None,
        )

        assert result is None
        assert calls == ["deep_observation", "observation_side_effects:positive"]

    asyncio.run(scenario())


def _private_identity() -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="onebot:bot-1:private:user-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )


def _group_identity() -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="onebot:bot-1:group:group-1",
        platform="onebot",
        bot_id="bot-1",
        scene_type="group",
        scene_id="group-1",
        subject_id=None,
    )


def _belief_action_count() -> int:
    with database_runtime.connect_sync() as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM ai_memory_belief_action"
        ).fetchone()
    assert row is not None
    return int(row[0])


def _belief_actions() -> list[str]:
    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            "SELECT action FROM ai_memory_belief_action ORDER BY id"
        ).fetchall()
    return [str(row[0]) for row in rows]


@dataclass(slots=True)
class _PolicyStub:
    action: str
    reason_code: str
    should_reply: bool
    should_observe: bool
    evidence: dict[str, object] = field(default_factory=dict)

    def evaluate(self, *, ingress_input: object) -> object:
        from apeiria.app.ai.runtime.stages import RuntimePolicyOutcome
        from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision

        return RuntimePolicyOutcome(
            stage="policy",
            source=ingress_input.turn.source,
            decision=RuntimeHardRuleDecision(
                action=self.action,
                reason_codes=(self.reason_code,),
                reason_text=self.reason_code,
                evidence=self.evidence,
                should_observe=self.should_observe,
                should_reply=self.should_reply,
            ),
        )

    async def decide_reply(self, *, social_input: object) -> object:
        del social_input

        from apeiria.app.ai.reply_strategy.models import ReplyStrategyDecision

        return ReplyStrategyDecision(
            action="reply",
            should_speak=True,
            tool_mode="allow",
            reason_codes=("test",),
            reason_text="test",
            evidence={},
            decision_source="fallback",
        )


@dataclass(slots=True)
class _ObservationStub:
    calls: list[str]

    async def apply(self, *, ingress_input: object) -> None:
        sentiment = ingress_input.turn.sentiment
        if sentiment is None:
            self.calls.append("observation_side_effects")
            return
        self.calls.append(f"observation_side_effects:{sentiment.polarity}")

    async def apply_observed_turn(self, *, ingress_input: object) -> None:
        del ingress_input
        self.calls.append("observed_turn")

    async def apply_deep_observation(self, *, ingress_input: object) -> object:
        del ingress_input

        from apeiria.ai.memory import AIMemoryExtractionResult, AIMessageSentiment

        self.calls.append("deep_observation")
        return AIMemoryExtractionResult(
            candidates=[],
            sentiment=AIMessageSentiment(polarity="positive", intensity=0.7),
            self_introduction_name=None,
        )


class _ContextStub:
    async def assemble(self, *, ingress_input: object) -> object:
        from apeiria.ai.model import AIModelBindingTarget
        from apeiria.ai.tools import AIToolPolicy
        from apeiria.app.ai.runtime.context.relationships import AIRelationshipTarget
        from apeiria.app.ai.runtime.session.context import RuntimeContextMaterials
        from apeiria.app.ai.runtime.stages import RuntimeContextBundle

        return RuntimeContextBundle(
            stage="context",
            context=RuntimeContextMaterials(
                turns=[],
                conversation_summary=None,
                relationship_target=AIRelationshipTarget(
                    platform=ingress_input.turn.identity.platform,
                    group_id=None,
                    user_id=ingress_input.turn.user_id,
                    is_private=ingress_input.turn.identity.scene_type == "private",
                ),
                model_target=AIModelBindingTarget(
                    conversation_id=ingress_input.turn.identity.session_id,
                    group_id=None,
                    user_id=ingress_input.turn.user_id,
                ),
                tool_policy=AIToolPolicy(),
                persona=None,
                recalled_memories=[],
                relationship_context=None,
                person_profile=(),
                allowed_tools=(),
                initiative_bias=0.0,
            ),
        )


@dataclass(slots=True)
class _PlanningStub:
    return_plan: bool

    async def plan(self, *, planning_input: object) -> object | None:
        del planning_input
        if not self.return_plan:
            return None
        raise _UnexpectedPlanCreationError


class _TraceStub:
    def project(self, *, trace_input: object) -> object:
        from apeiria.app.ai.runtime.stages import RuntimeTraceOutcome
        from apeiria.app.ai.runtime.trace import project_turn_trace

        return RuntimeTraceOutcome(
            stage="trace",
            trace=project_turn_trace(
                session_id=trace_input.turn.identity.session_id,
                strategy_decision=trace_input.strategy_decision,
                turn_result=trace_input.turn_result,
                trace_id=trace_input.trace_id,
                runtime_mode=trace_input.turn.runtime_mode,
                delivery_result=trace_input.delivery_result,
            ),
        )


class _UnexpectedPlanCreationError(AssertionError):
    """Raised when a test unexpectedly requests a runtime plan."""
