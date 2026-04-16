"""Capability bridge tool handler — plugin.capability."""

from __future__ import annotations

import asyncio
from typing import Annotated, Any

from apeiria.app.ai.tools.decorators import ai_tool
from apeiria.app.ai.tools.models import AIToolExecutionContext, AIToolResult

_DEFAULT_TIMEOUT_SECONDS = 5.0


@ai_tool(
    name="plugin.capability",
    description="invoke a whitelisted NoneBot capability bridge",
    read_only=False,
    concurrency_safe=False,
    risk_level="high",
    is_capability_bridge=True,
)
async def handle_capability(
    capability_name: Annotated[str, "The registered capability name to invoke."],
    arguments: Annotated[
        dict[str, Any] | None,
        "Structured arguments for the capability.",
    ] = None,
    *,
    context: AIToolExecutionContext,
) -> AIToolResult:
    """Invoke a whitelisted NoneBot capability via the bridge."""

    from apeiria.app.ai.tools.bridge import invoke_skill_with_policy
    from apeiria.app.ai.tools.models import AINoneBotCapabilityRequest
    from apeiria.app.ai.tools.service import ai_tool_service

    request = AINoneBotCapabilityRequest(
        capability_name=capability_name,
        arguments=arguments or {},
    )

    try:
        result = await asyncio.wait_for(
            invoke_skill_with_policy(
                registry=ai_tool_service.registry,
                bridge=ai_tool_service.capability_bridge,
                request=request,
                policy=context.policy,
            ),
            timeout=_DEFAULT_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return AIToolResult(
            summary=(
                f"- [plugin.capability] {capability_name} timed out after "
                f"{_DEFAULT_TIMEOUT_SECONDS:.1f}s"
            ),
            output_payload={
                "capability_name": capability_name,
                "error": "timeout",
                "timeout_seconds": _DEFAULT_TIMEOUT_SECONDS,
            },
            status="timeout",
        )
    except Exception as exc:  # noqa: BLE001
        return AIToolResult(
            summary=(f"- [plugin.capability] {capability_name} failed: {exc}"),
            output_payload={
                "capability_name": capability_name,
                "error": str(exc),
            },
            status="error",
        )

    if isinstance(result, dict):
        summary_parts = ", ".join(f"{k}={v}" for k, v in sorted(result.items()))
        summary = f"- [plugin.capability] {capability_name}: {summary_parts}"
    else:
        summary = f"- [plugin.capability] {capability_name}: {result}"

    return AIToolResult(
        summary=summary,
        output_payload={
            "capability_name": capability_name,
            "result": result,
        },
    )
