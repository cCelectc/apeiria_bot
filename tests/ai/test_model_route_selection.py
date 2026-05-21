from __future__ import annotations

import asyncio
from random import Random
from typing import TYPE_CHECKING

from apeiria.ai.model.catalog.models import AIChatModelDefinition
from apeiria.ai.model.routing.bindings import (
    AIModelBindingTarget,
    resolve_model_route_binding,
)
from apeiria.ai.model.routing.models import (
    AIModelProfileDefinition,
    AIModelRouteBindingSpec,
    AIModelRouteDefinition,
    AIModelRouteMemberDefinition,
    AIModelRouteQuery,
)
from apeiria.ai.model.routing.selection import (
    AIModelAttemptPlan,
    resolve_model_route_attempt_plan,
)
from apeiria.ai.model.sources.models import AISourceDefinition
from apeiria.app.ai.runtime.planning import model_selection

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_model_route_binding_prefers_conversation_over_global() -> None:
    target = AIModelBindingTarget(
        conversation_id="conversation-1",
        group_id="group-1",
        user_id="user-1",
    )

    binding = resolve_model_route_binding(
        [
            AIModelRouteBindingSpec(
                binding_id="global",
                scope_type="global",
                scope_id="__global__",
                task_class="reply_default",
                route_id="route-global",
            ),
            AIModelRouteBindingSpec(
                binding_id="conversation",
                scope_type="conversation",
                scope_id="conversation-1",
                task_class="reply_default",
                route_id="route-conversation",
            ),
        ],
        target,
        task_class="reply_default",
    )

    assert binding is not None
    assert binding.route_id == "route-conversation"


def test_primary_fallback_route_preserves_member_order() -> None:
    plan = resolve_model_route_attempt_plan(
        _route(mode="primary_fallback", algorithm="ordered"),
        (
            _member("member-a", "profile-a", position=0),
            _member("member-b", "profile-b", position=1),
            _member("member-c", "profile-c", position=2),
        ),
        (
            _profile("profile-a", "model-a"),
            _profile("profile-b", "model-b"),
            _profile("profile-c", "model-c"),
        ),
        (_source(),),
        (
            _model("model-a", "gpt-a"),
            _model("model-b", "gpt-b"),
            _model("model-c", "gpt-c"),
        ),
    )

    assert plan is not None
    assert plan.selected.profile.profile_id == "profile-a"
    assert [item.profile.profile_id for item in plan.fallback_models] == [
        "profile-b",
        "profile-c",
    ]


def test_primary_fallback_route_skips_disabled_and_unresolvable_members() -> None:
    plan = resolve_model_route_attempt_plan(
        _route(mode="primary_fallback", algorithm="ordered"),
        (
            _member("member-a", "profile-disabled", position=0),
            _member("member-b", "profile-missing-model", position=1),
            _member("member-c", "profile-c", position=2),
        ),
        (
            _profile("profile-disabled", "model-a", enabled=False),
            _profile("profile-missing-model", "missing-model"),
            _profile("profile-c", "model-c"),
        ),
        (_source(),),
        (_model("model-c", "gpt-c"),),
    )

    assert plan is not None
    assert plan.selected.profile.profile_id == "profile-c"
    assert plan.fallback_models == ()


def test_load_balanced_route_uses_weighted_selection_with_ordered_fallbacks() -> None:
    plan = resolve_model_route_attempt_plan(
        _route(mode="load_balance", algorithm="weighted_random"),
        (
            _member("member-a", "profile-a", position=0, weight=1),
            _member("member-b", "profile-b", position=1, weight=9),
            _member("member-c", "profile-c", position=2, weight=1),
        ),
        (
            _profile("profile-a", "model-a"),
            _profile("profile-b", "model-b"),
            _profile("profile-c", "model-c"),
        ),
        (_source(),),
        (
            _model("model-a", "gpt-a"),
            _model("model-b", "gpt-b"),
            _model("model-c", "gpt-c"),
        ),
        randomizer=Random(0),
    )

    assert plan is not None
    assert plan.selected.profile.profile_id == "profile-b"
    assert [item.profile.profile_id for item in plan.fallback_models] == [
        "profile-a",
        "profile-c",
    ]


def test_route_can_disable_failure_fallbacks() -> None:
    plan = resolve_model_route_attempt_plan(
        _route(
            mode="primary_fallback",
            algorithm="ordered",
            fallback_on_failure=False,
        ),
        (
            _member("member-a", "profile-a", position=0),
            _member("member-b", "profile-b", position=1),
        ),
        (
            _profile("profile-a", "model-a"),
            _profile("profile-b", "model-b"),
        ),
        (_source(),),
        (
            _model("model-a", "gpt-a"),
            _model("model-b", "gpt-b"),
        ),
    )

    assert plan is not None
    assert plan.selected.profile.profile_id == "profile-a"
    assert plan.fallback_models == ()


def test_select_task_model_uses_route_attempt_plan(
    monkeypatch: "MonkeyPatch",
) -> None:
    selected = resolve_model_route_attempt_plan(
        _route(mode="primary_fallback", algorithm="ordered"),
        (_member("member-a", "profile-a", position=0),),
        (_profile("profile-a", "model-a"),),
        (_source(),),
        (_model("model-a", "gpt-a"),),
    )
    assert selected is not None

    class RouteService:
        async def resolve_attempt_plan(
            self,
            query: AIModelRouteQuery,
            *,
            target: AIModelBindingTarget | None = None,
        ) -> AIModelAttemptPlan | None:
            assert query.task_class == "reply_default"
            assert target is None
            return selected

    monkeypatch.setattr(model_selection, "ai_model_route_service", RouteService())

    result = asyncio.run(model_selection.select_task_model(task_class="reply_default"))

    assert result is not None
    assert result.profile.profile_id == "profile-a"


def _route(
    *,
    mode: str,
    algorithm: str,
    fallback_on_failure: bool = True,
) -> AIModelRouteDefinition:
    return AIModelRouteDefinition(
        route_id="route-1",
        name="Default reply",
        task_class="reply_default",
        mode=mode,  # type: ignore[arg-type]
        algorithm=algorithm,  # type: ignore[arg-type]
        fallback_on_failure=fallback_on_failure,
        enabled=True,
    )


def _member(
    member_id: str,
    profile_id: str,
    *,
    position: int,
    weight: int = 1,
    enabled: bool = True,
) -> AIModelRouteMemberDefinition:
    return AIModelRouteMemberDefinition(
        route_member_id=member_id,
        route_id="route-1",
        profile_id=profile_id,
        position=position,
        weight=weight,
        enabled=enabled,
    )


def _profile(
    profile_id: str,
    model_id: str,
    *,
    enabled: bool = True,
) -> AIModelProfileDefinition:
    return AIModelProfileDefinition(
        profile_id=profile_id,
        name=profile_id,
        model_id=model_id,
        task_class="reply_default",
        priority=10,
        enabled=enabled,
    )


def _source() -> AISourceDefinition:
    return AISourceDefinition(
        source_id="source-1",
        name="Primary",
        capability_type="chat_completion",
        client_type="openai",
        preset_type="openai_compatible",
        api_base=None,
        enabled=True,
        adapter_kind="openai_compatible",
    )


def _model(model_id: str, identifier: str) -> AIChatModelDefinition:
    return AIChatModelDefinition(
        model_id=model_id,
        source_id="source-1",
        model_identifier=identifier,
        display_name=identifier,
        enabled=True,
    )
