"""Tool execution recording and host-action service."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from nonebot.log import logger

from apeiria.ai.capabilities import (
    AICapabilityBindingRegistry,
    AICapabilityBindingSnapshot,
    AICapabilityBindingType,
    AICapabilityContract,
    AICapabilityContractRegistry,
    AICapabilityContractSnapshot,
)
from apeiria.ai.tools.capabilities import register_builtin_capabilities
from apeiria.ai.tools.contracts import AIToolExecutionCreateInput
from apeiria.ai.tools.debug import AICapabilityPreview
from apeiria.ai.tools.execution import AIToolIntentExecutor
from apeiria.ai.tools.execution_repository import AIToolExecutionRepository
from apeiria.ai.tools.host_actions import AIHostActionRegistry
from apeiria.ai.tools.models import (
    AIToolExecutionRequest,
    AIToolExecutionView,
    AIToolIntent,
    AIToolObservationResult,
    AIToolPolicy,
    AIToolTurnCreateInput,
)
from apeiria.ai.tools.policy import evaluate_tool_policy
from apeiria.ai.tools.registry import AIToolRegistry


class AIToolService:
    """Runtime tool registry, policy, and execution service.

    Tool handlers are registered declaratively via ``@ai_tool`` decorators
    in the ``handlers/`` package.  This class provides unified dispatch,
    death-spiral detection, and execution recording.
    """

    def __init__(
        self,
        *,
        execution_repository: AIToolExecutionRepository | None = None,
        intent_executor: AIToolIntentExecutor | None = None,
    ) -> None:
        self.registry = AIToolRegistry()
        self.host_action_registry = AIHostActionRegistry()
        self._execution_repository = execution_repository or AIToolExecutionRepository()
        self._intent_executor = intent_executor or AIToolIntentExecutor()
        register_builtin_capabilities(self.host_action_registry)
        self._load_declarative_tools()

    def _load_declarative_tools(self) -> None:
        """Import handler modules and register all @ai_tool decorated specs."""

        count = self.registry.register_pending_tools()
        logger.debug("Registered {} declarative AI tools", count)

    def list_tool_specs(
        self,
        policy: AIToolPolicy | None = None,
    ) -> list[AICapabilityContract]:
        if policy is None:
            return list(self.contract_snapshot().contracts)
        return self.list_allowed_tools(policy)

    def list_allowed_tools(self, policy: AIToolPolicy) -> list[AICapabilityContract]:
        return [
            tool
            for tool in self.contract_snapshot().contracts
            if evaluate_tool_policy(
                tool,
                policy,
                binding_type=self._binding_type_for_contract(tool.name),
            ).allowed
        ]

    def contract_snapshot(self) -> AICapabilityContractSnapshot:
        contracts = AICapabilityContractRegistry(
            tuple(self.registry.contract_snapshot().contracts)
        )
        for record in self.host_action_registry.snapshot().ready_actions:
            if (
                record.contract is not None
                and contracts.get(record.contract.name) is None
            ):
                contracts.register(record.contract)
        return contracts.snapshot()

    def binding_snapshot(self) -> AICapabilityBindingSnapshot:
        bindings = AICapabilityBindingRegistry(
            tuple(self.registry.binding_snapshot().bindings)
        )
        for record in self.host_action_registry.snapshot().ready_actions:
            if (
                record.binding is not None
                and bindings.get(record.binding.binding_key) is None
            ):
                bindings.register(record.binding)
        return bindings.snapshot()

    def _binding_type_for_contract(
        self,
        contract_name: str,
    ) -> AICapabilityBindingType | None:
        binding = self.binding_snapshot().by_contract.get(contract_name)
        return binding.binding_type if binding is not None else None

    # ------------------------------------------------------------------
    # Unified tool execution with death-spiral detection
    # ------------------------------------------------------------------

    async def execute_tool_intents(
        self,
        *,
        request: AIToolExecutionRequest,
        intents: list[AIToolIntent],
    ) -> list[AIToolObservationResult]:
        observations = await self._intent_executor.execute_tool_intents(
            registry=self.registry,
            bindings=dict(self.binding_snapshot().by_contract),
            request=request,
            intents=intents,
        )

        for observation in observations:
            await self.record_execution(
                AIToolExecutionCreateInput(
                    session_id=request.session_id,
                    tool_name=observation.tool_name,
                    status=observation.status,
                    trace_id=request.trace_id,
                    input_payload=observation.input_payload,
                    output_payload=observation.output_payload,
                ),
            )

        return observations

    # ------------------------------------------------------------------
    # Turn building
    # ------------------------------------------------------------------

    def build_tool_turns(
        self,
        observations: list[AIToolObservationResult],
    ) -> list[AIToolTurnCreateInput]:
        return [
            AIToolTurnCreateInput(
                author_id="ai_tool_observation",
                text_content=observation.summary,
                meta={
                    "source": "tool_observation",
                    "trace_id": (
                        observation.output_payload.get("trace_id")
                        if isinstance(observation.output_payload, dict)
                        else None
                    ),
                    "tool_name": observation.tool_name,
                    "status": observation.status,
                    "input": _to_jsonable_payload(observation.input_payload),
                    "output": _to_jsonable_payload(observation.output_payload),
                },
            )
            for observation in observations
        ]

    # ------------------------------------------------------------------
    # Execution recording
    # ------------------------------------------------------------------

    async def record_execution(
        self,
        create_input: AIToolExecutionCreateInput,
    ) -> AIToolExecutionView:
        return self._execution_repository.record_execution(create_input)

    async def list_executions(
        self,
        *,
        session_id: str,
    ) -> list[AIToolExecutionView]:
        return self._execution_repository.list_executions(session_id=session_id)

    # ------------------------------------------------------------------
    # Capability preview
    # ------------------------------------------------------------------

    def preview_capability(
        self,
        *,
        capability_name: str,
        policy: AIToolPolicy,
    ) -> AICapabilityPreview:
        registered = self.host_action_registry.can_handle(capability_name)
        tool = self.contract_snapshot().by_name.get(capability_name)
        if not registered:
            return AICapabilityPreview(
                capability_name=capability_name,
                registered=False,
                allowed=False,
                reason="capability is not registered",
                allow_host_actions=policy.allow_host_actions,
                execution_enabled=policy.execution_enabled,
            )
        if tool is None:
            return AICapabilityPreview(
                capability_name=capability_name,
                registered=True,
                allowed=False,
                reason="capability tool binding is missing",
                allow_host_actions=policy.allow_host_actions,
                execution_enabled=policy.execution_enabled,
            )

        allowed_tools = self.list_allowed_tools(policy)
        allowed_tool_names = {item.name for item in allowed_tools}
        allowed = tool.name in allowed_tool_names
        reason = (
            "allowed by current tool policy"
            if allowed
            else "denied by current tool policy"
        )
        return AICapabilityPreview(
            capability_name=capability_name,
            registered=True,
            allowed=allowed,
            reason=reason,
            allow_host_actions=policy.allow_host_actions,
            execution_enabled=policy.execution_enabled,
        )


ai_tool_service = AIToolService()


def _to_jsonable_payload(payload: Any) -> Any:
    if is_dataclass(payload) and not isinstance(payload, type):
        return asdict(payload)
    return payload
