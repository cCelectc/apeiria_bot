"""Pure in-memory executable capability registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from apeiria.ai.capabilities import (
    AICapabilityBinding,
    AICapabilityBindingRegistry,
    AICapabilityBindingSnapshot,
    AICapabilityContract,
    AICapabilityContractRegistry,
    AICapabilityContractSnapshot,
    create_local_tool_binding,
)

if TYPE_CHECKING:
    from apeiria.ai.capabilities import AILocalToolHandler
    from apeiria.ai.tools.models import AIToolOrigin


@dataclass(frozen=True)
class AILocalToolDeclaration:
    """Local executable capability declaration collected by decorators."""

    contract: AICapabilityContract
    binding: AICapabilityBinding


class AIToolRegistry:
    """Registry for AI-visible executable capability contracts and bindings.

    Supports both direct ``register()`` calls and bulk registration
    from the ``@ai_tool`` decorator via ``register_pending_tools()``.
    """

    def __init__(self) -> None:
        self._contracts = AICapabilityContractRegistry()
        self._bindings = AICapabilityBindingRegistry()

    def register(self, declaration: AILocalToolDeclaration) -> None:
        self._contracts.register(declaration.contract)
        self._bindings.register(declaration.binding)

    def register_contract_and_binding(
        self,
        *,
        contract: AICapabilityContract,
        binding: AICapabilityBinding,
    ) -> None:
        """Register one executable capability contract and binding."""

        self.register(AILocalToolDeclaration(contract=contract, binding=binding))

    def get(self, name: str) -> AICapabilityContract | None:
        return self._contracts.get(name)

    def get_binding_for_contract(self, name: str) -> AICapabilityBinding | None:
        return self._bindings.get_for_contract(name)

    def list_tools(self) -> list[AICapabilityContract]:
        return list(self.contract_snapshot().contracts)

    def list_by_origin(self, origin: "AIToolOrigin") -> list[AICapabilityContract]:
        return [
            contract
            for contract in self.list_tools()
            if contract.origin.value == origin
        ]

    def contract_snapshot(self) -> AICapabilityContractSnapshot:
        return self._contracts.snapshot()

    def binding_snapshot(self) -> AICapabilityBindingSnapshot:
        return self._bindings.snapshot()

    def register_pending_tools(self) -> int:
        """Import handler modules and register all ``@ai_tool`` declarations.

        Returns the number of newly registered tools.
        """

        from apeiria.ai.tools.decorators import collect_pending_tools
        from apeiria.ai.tools.handlers import ensure_handlers_loaded

        ensure_handlers_loaded()
        pending: list[Any] = collect_pending_tools()
        count = 0
        for declaration in pending:
            self.register(declaration)
            count += 1
        return count


def local_tool_declaration(
    *,
    contract: AICapabilityContract,
    handler: "AILocalToolHandler",
) -> AILocalToolDeclaration:
    """Build a local-tool declaration with a standard binding key."""

    return AILocalToolDeclaration(
        contract=contract,
        binding=create_local_tool_binding(
            contract_name=contract.name,
            binding_key=f"local:{contract.name}",
            handler=handler,
        ),
    )


__all__ = [
    "AILocalToolDeclaration",
    "AIToolRegistry",
    "local_tool_declaration",
]
