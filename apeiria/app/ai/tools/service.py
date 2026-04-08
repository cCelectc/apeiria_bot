"""Tool execution recording and capability bridge service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import timezone
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.tools.bridge import (
    AINoneBotCapabilityBridge,
    invoke_capability_with_policy,
)
from apeiria.app.ai.tools.models import (
    AINoneBotCapabilityRequest,
    AIToolExecutionView,
    AIToolPolicy,
    AIToolSpec,
)
from apeiria.app.ai.tools.policy import evaluate_tool_policy
from apeiria.app.ai.tools.registry import AIToolRegistry
from apeiria.infra.db.models import AIToolExecution

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class AIToolExecutionCreateInput:
    """Create payload for one persisted tool execution record."""

    conversation_id: str
    tool_name: str
    status: str
    input_payload: Any | None = None
    output_payload: Any | None = None


class AIToolService:
    """Tool registry, policy, and execution record service."""

    def __init__(self) -> None:
        self.registry = AIToolRegistry()
        self.capability_bridge = AINoneBotCapabilityBridge()
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register built-in AI-visible tool declarations."""

        for tool in (
            AIToolSpec(
                name="memory.query",
                description="inspect recalled long-term memory",
                read_only=True,
                concurrency_safe=True,
            ),
            AIToolSpec(
                name="relationship.inspect",
                description="inspect current affinity and mood projection",
                read_only=True,
                concurrency_safe=True,
            ),
            AIToolSpec(
                name="plugin.capability",
                description="invoke a whitelisted NoneBot capability bridge",
                read_only=False,
                concurrency_safe=False,
                risk_level="high",
                is_capability_bridge=True,
            ),
        ):
            self.registry.register(tool)

    def list_allowed_tools(self, policy: AIToolPolicy) -> list[AIToolSpec]:
        """List the tools allowed under one scene policy."""

        return [
            tool
            for tool in self.registry.list_tools()
            if evaluate_tool_policy(tool, policy).allowed
        ]

    async def invoke_capability(
        self,
        *,
        request: AINoneBotCapabilityRequest,
        policy: AIToolPolicy,
    ) -> Any:
        """Invoke one registered capability through the whitelist bridge."""

        return await invoke_capability_with_policy(
            registry=self.registry,
            bridge=self.capability_bridge,
            request=request,
            policy=policy,
        )

    async def record_execution(
        self,
        session: AsyncSession,
        create_input: AIToolExecutionCreateInput,
    ) -> AIToolExecution:
        """Persist one tool execution record."""

        row = AIToolExecution(
            execution_id=f"tool_exec_{uuid4().hex}",
            conversation_id=create_input.conversation_id,
            tool_name=create_input.tool_name,
            status=create_input.status,
            input_json=(
                json.dumps(
                    create_input.input_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if create_input.input_payload is not None
                else None
            ),
            output_json=(
                json.dumps(
                    create_input.output_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if create_input.output_payload is not None
                else None
            ),
        )
        session.add(row)
        await session.flush()
        return row

    async def list_executions(
        self,
        session: AsyncSession,
        *,
        conversation_id: str,
    ) -> list[AIToolExecutionView]:
        """List persisted tool executions for one conversation."""

        result = await session.execute(
            select(AIToolExecution)
            .where(AIToolExecution.conversation_id == conversation_id)
            .order_by(AIToolExecution.created_at.asc(), AIToolExecution.id.asc())
        )
        rows = result.scalars().all()
        return [
            AIToolExecutionView(
                execution_id=row.execution_id,
                conversation_id=row.conversation_id,
                tool_name=row.tool_name,
                status=row.status,
                input_json=row.input_json,
                output_json=row.output_json,
                created_at=(
                    row.created_at.replace(tzinfo=timezone.utc)
                    if row.created_at.tzinfo is None
                    else row.created_at
                ),
            )
            for row in rows
        ]


ai_tool_service = AIToolService()
