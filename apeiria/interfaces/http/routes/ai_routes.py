"""AI admin routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from fastapi import APIRouter, Depends, HTTPException, Query, status

from apeiria.app.ai.admin.service import (
    AISourceDeleteBlockedError,
    AISourceModelDeleteBlockedError,
    AISourceModelFetchConfigError,
    AISourceModelFetchUpstreamError,
    AISourceModelTestConfigError,
    AISourceModelTestUpstreamError,
    ai_admin_service,
)
from apeiria.app.ai.tools.models import AIToolPolicy
from apeiria.interfaces.http.auth import require_control_panel
from apeiria.interfaces.http.routes.ai_route_support import (
    to_ai_capability_item,
    to_ai_capability_preview_item,
    to_ai_chat_message_item,
    to_ai_future_task_item,
    to_ai_memory_item,
    to_ai_model_binding_item,
    to_ai_model_catalog_item,
    to_ai_model_profile_item,
    to_ai_person_profile_item,
    to_ai_persona_binding_item,
    to_ai_persona_item,
    to_ai_recent_target_item,
    to_ai_relationship_event_item,
    to_ai_relationship_state_item,
    to_ai_session_item,
    to_ai_session_prompt_preview_item,
    to_ai_skill_item,
    to_ai_source_item,
    to_ai_source_model_item,
    to_ai_source_preset_item,
    to_ai_tool_execution_item,
    to_ai_tool_intent_preview_item,
    to_ai_tool_item,
    to_ai_tool_policy_binding_item,
    to_ai_tool_policy_preview_item,
)
from apeiria.interfaces.http.schemas.ai_models import (
    AICapabilityItem,
    AICapabilityPreviewItem,
    AICapabilityPreviewRequest,
    AIChatMessageItem,
    AIFutureTaskItem,
    AIMemoryBulkActionRequest,
    AIMemoryBulkActionResult,
    AIMemoryBulkIgnoreRequest,
    AIMemoryCreateRequest,
    AIMemoryDeleteResult,
    AIMemoryItem,
    AIMemoryToggleIgnoredRequest,
    AIMemoryUpdateRequest,
    AIModelBindingItem,
    AIModelCatalogItem,
    AIModelProfileItem,
    AIModelProfileUpsertRequest,
    AIPersonaBindingItem,
    AIPersonaItem,
    AIPersonaUpsertRequest,
    AIPersonProfileItem,
    AIPersonProfileUpdateRequest,
    AIRecentTargetItem,
    AIRelationshipEventItem,
    AIRelationshipScoreUpdateRequest,
    AIRelationshipStateItem,
    AISessionItem,
    AISessionPromptPreviewItem,
    AISkillItem,
    AISourceItem,
    AISourceModelFetchRequest,
    AISourceModelItem,
    AISourceModelTestRequest,
    AISourceModelTestResult,
    AISourceModelUpsertRequest,
    AISourcePresetItem,
    AISourceUpsertRequest,
    AIToolExecutionItem,
    AIToolIntentPreviewItem,
    AIToolIntentPreviewRequest,
    AIToolItem,
    AIToolPolicyBindingCreateRequest,
    AIToolPolicyBindingItem,
    AIToolPolicyBindingUpdateRequest,
    AIToolPolicyPreviewItem,
    AIToolPolicyPreviewRequest,
)

if TYPE_CHECKING:
    from apeiria.shared.principal import AuthSession

router = APIRouter()


def _actor_username_from_claims(session: AuthSession) -> str | None:
    username = session.username.strip()
    return username or None






@router.get("/recent-targets", response_model=list[AIRecentTargetItem])
async def list_ai_recent_targets(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AIRecentTargetItem]:
    targets = await ai_admin_service.list_recent_targets(limit=limit)
    return [to_ai_recent_target_item(item) for item in targets]


@router.get("/scenes", response_model=list[AISessionItem])
async def list_ai_scenes(
    _: Annotated[Any, Depends(require_control_panel)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[AISessionItem]:
    conversations = await ai_admin_service.list_recent_sessions(limit=limit)
    return [to_ai_session_item(item) for item in conversations]


@router.get("/scenes/turns", response_model=list[AIChatMessageItem])
async def list_ai_scene_turns(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[AIChatMessageItem]:
    turns = await ai_admin_service.list_scene_turns(
        scene_id=scene_id,
        limit=limit,
    )
    return [to_ai_chat_message_item(item) for item in turns]


@router.get(
    "/scenes/prompt-preview",
    response_model=AISessionPromptPreviewItem | None,
)
async def get_ai_scene_prompt_preview(
    _: Annotated[Any, Depends(require_control_panel)],
    scene_id: Annotated[str, Query(min_length=1)],
    turn_limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AISessionPromptPreviewItem | None:
    preview = await ai_admin_service.build_scene_prompt_preview(
        scene_id=scene_id,
        turn_limit=turn_limit,
    )
    if preview is None:
        return None
    return to_ai_session_prompt_preview_item(preview)








from apeiria.interfaces.http.routes.ai_future_tasks_routes import router as _future_tasks_router
from apeiria.interfaces.http.routes.ai_person_profiles_routes import router as _person_profiles_router
from apeiria.interfaces.http.routes.ai_personas_routes import router as _personas_router
from apeiria.interfaces.http.routes.ai_relationships_routes import router as _relationships_router

router.include_router(_future_tasks_router)
router.include_router(_person_profiles_router)
router.include_router(_personas_router)
router.include_router(_relationships_router)
from apeiria.interfaces.http.routes.ai_memories_routes import router as _memories_router
from apeiria.interfaces.http.routes.ai_tools_routes import router as _tools_router

router.include_router(_memories_router)
router.include_router(_tools_router)
from apeiria.interfaces.http.routes.ai_models_routes import router as _models_router
from apeiria.interfaces.http.routes.ai_sources_routes import router as _sources_router

router.include_router(_models_router)
router.include_router(_sources_router)
