"""Shared prompt assembly capability."""

from __future__ import annotations

from .conversation_summary import (
    ConversationSummaryPromptInput,
    build_conversation_summary_packet,
)
from .memory_extraction import (
    MemoryExtractionPromptInput,
    build_memory_extraction_packet,
)
from .models import PromptPacket, PromptPurpose, PromptSection, PromptSectionRole
from .regions import (
    PromptRegion,
    PromptRegionProjection,
    project_prompt_regions,
    prompt_region_diagnostics,
)
from .renderer import render_flat, render_messages
from .reply import (
    ReplyPersonaPromptBundleLike,
    ReplyPromptInput,
    ReplyPromptMode,
    build_reply_final_packet,
    build_reply_planner_packet,
    project_reply_prompt_regions,
)
from .skill_selection import (
    SkillCatalogEntryLike,
    SkillSelectionPromptInput,
    build_skill_selection_packet,
)
from .social_judgment import (
    SocialEngagementType,
    SocialJudgmentPromptInput,
    build_social_judgment_packet,
)
from .tool_intent import (
    ToolIntentPlanningPromptInput,
    build_tool_intent_planning_packet,
)

__all__ = [
    "ConversationSummaryPromptInput",
    "MemoryExtractionPromptInput",
    "PromptPacket",
    "PromptPurpose",
    "PromptRegion",
    "PromptRegionProjection",
    "PromptSection",
    "PromptSectionRole",
    "ReplyPersonaPromptBundleLike",
    "ReplyPromptInput",
    "ReplyPromptMode",
    "SkillCatalogEntryLike",
    "SkillSelectionPromptInput",
    "SocialEngagementType",
    "SocialJudgmentPromptInput",
    "ToolIntentPlanningPromptInput",
    "build_conversation_summary_packet",
    "build_memory_extraction_packet",
    "build_reply_final_packet",
    "build_reply_planner_packet",
    "build_skill_selection_packet",
    "build_social_judgment_packet",
    "build_tool_intent_planning_packet",
    "project_prompt_regions",
    "project_reply_prompt_regions",
    "prompt_region_diagnostics",
    "render_flat",
    "render_messages",
]
