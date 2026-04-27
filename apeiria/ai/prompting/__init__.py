"""Shared prompt assembly capability."""

from __future__ import annotations

from .models import PromptPacket, PromptPurpose, PromptSection, PromptSectionRole
from .renderer import render_flat, render_messages
from .reply import (
    ReplyPersonaPromptBundleLike,
    ReplyPromptInput,
    ReplyPromptMode,
    build_reply_final_packet,
    build_reply_planner_packet,
)

__all__ = [
    "PromptPacket",
    "PromptPurpose",
    "PromptSection",
    "PromptSectionRole",
    "ReplyPersonaPromptBundleLike",
    "ReplyPromptInput",
    "ReplyPromptMode",
    "build_reply_final_packet",
    "build_reply_planner_packet",
    "render_flat",
    "render_messages",
]
