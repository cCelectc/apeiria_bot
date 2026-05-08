"""Shared structured-output contracts for auxiliary AI calls."""

from __future__ import annotations

from typing import Any

from apeiria.ai.model.runtime.capabilities import (
    AI_MODEL_RESPONSE_FORMAT_OPTION,
    AIModelCallOptions,
    json_schema_response_format,
)

SOCIAL_JUDGMENT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "action": {
            "type": "string",
            "enum": ["reply", "interject", "wait", "suppress"],
        },
        "tool_mode": {
            "type": "string",
            "enum": ["allow", "avoid"],
        },
        "reason_codes": {
            "type": "array",
            "items": {"type": "string", "minLength": 1, "maxLength": 64},
            "minItems": 1,
            "maxItems": 6,
        },
        "reason_text": {
            "type": "string",
            "minLength": 1,
            "maxLength": 240,
        },
        "evidence": {
            "type": "object",
            "additionalProperties": True,
        },
    },
    "required": [
        "action",
        "tool_mode",
        "reason_codes",
        "reason_text",
        "evidence",
    ],
    "additionalProperties": False,
}

MEMORY_EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "memories": {
            "type": "array",
            "maxItems": 5,
            "items": {
                "type": "object",
                "properties": {
                    "memory_kind": {
                        "type": "string",
                        "enum": [
                            "fact",
                            "preference",
                            "relationship",
                            "note",
                            "impression",
                        ],
                    },
                    "content": {"type": "string", "minLength": 1},
                    "action": {
                        "type": "string",
                        "enum": ["add", "update", "noop"],
                    },
                    "target_memory_id": {
                        "type": ["string", "null"],
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                    "salience": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                    },
                },
                "required": [
                    "memory_kind",
                    "content",
                    "confidence",
                    "salience",
                ],
                "additionalProperties": False,
            },
        },
        "sentiment": {
            "type": "object",
            "properties": {
                "polarity": {
                    "type": "string",
                    "enum": ["positive", "neutral", "negative", "playful"],
                },
                "intensity": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": ["polarity", "intensity"],
            "additionalProperties": False,
        },
        "self_introduction_name": {
            "type": ["string", "null"],
        },
    },
    "required": ["memories", "sentiment", "self_introduction_name"],
    "additionalProperties": False,
}

SKILL_SELECTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "selected_names": {
            "type": "array",
            "items": {
                "type": "string",
                "minLength": 1,
                "maxLength": 128,
            },
            "maxItems": 8,
        },
    },
    "required": ["selected_names"],
    "additionalProperties": False,
}


def auxiliary_json_schema_options(
    *,
    name: str,
    schema: dict[str, Any],
) -> AIModelCallOptions:
    """Build optional JSON-schema options for one auxiliary model call."""

    return AIModelCallOptions(
        values={
            AI_MODEL_RESPONSE_FORMAT_OPTION: json_schema_response_format(
                name=name,
                schema=schema,
            )
        }
    )


__all__ = [
    "MEMORY_EXTRACTION_SCHEMA",
    "SKILL_SELECTION_SCHEMA",
    "SOCIAL_JUDGMENT_SCHEMA",
    "auxiliary_json_schema_options",
]
