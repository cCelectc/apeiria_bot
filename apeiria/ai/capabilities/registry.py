"""Capability contract and binding registries."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from .bindings import AICapabilityBinding, AICapabilityBindingSnapshot

if TYPE_CHECKING:
    from collections.abc import Mapping

    from .contracts import AICapabilityContract


class AIDuplicateCapabilityContractError(ValueError):
    """Raised when a capability contract name is registered twice."""


class AIDuplicateCapabilityBindingError(ValueError):
    """Raised when a capability binding key or contract is registered twice."""


@dataclass(frozen=True)
class AICapabilityContractSnapshot:
    """Immutable contract registry read model."""

    contracts: tuple[AICapabilityContract, ...]
    by_name: Mapping[str, AICapabilityContract]


class AICapabilityContractRegistry:
    """Mutable builder for provider-neutral capability contracts."""

    def __init__(
        self,
        contracts: tuple["AICapabilityContract", ...] = (),
    ) -> None:
        self._contracts: dict[str, AICapabilityContract] = {}
        for contract in contracts:
            self.register(contract)

    def register(self, contract: "AICapabilityContract") -> None:
        """Register one contract by stable name."""

        if contract.name in self._contracts:
            raise AIDuplicateCapabilityContractError(contract.name)
        self._contracts[contract.name] = contract

    def get(self, name: str) -> "AICapabilityContract | None":
        """Return one registered contract by name."""

        return self._contracts.get(name)

    def snapshot(self) -> AICapabilityContractSnapshot:
        """Return an immutable read snapshot sorted by contract name."""

        contracts = tuple(self._contracts[name] for name in sorted(self._contracts))
        return AICapabilityContractSnapshot(
            contracts=contracts,
            by_name=MappingProxyType(
                {contract.name: contract for contract in contracts}
            ),
        )


class AICapabilityBindingRegistry:
    """Mutable builder for capability fulfillment bindings."""

    def __init__(
        self,
        bindings: tuple[AICapabilityBinding, ...] = (),
    ) -> None:
        self._bindings: dict[str, AICapabilityBinding] = {}
        self._contract_bindings: dict[str, AICapabilityBinding] = {}
        for binding in bindings:
            self.register(binding)

    def register(self, binding: AICapabilityBinding) -> None:
        """Register one binding by key and contract name."""

        if binding.binding_key in self._bindings:
            raise AIDuplicateCapabilityBindingError(binding.binding_key)
        if binding.contract_name in self._contract_bindings:
            raise AIDuplicateCapabilityBindingError(binding.contract_name)
        self._bindings[binding.binding_key] = binding
        self._contract_bindings[binding.contract_name] = binding

    def get(self, binding_key: str) -> AICapabilityBinding | None:
        """Return one registered binding by key."""

        return self._bindings.get(binding_key)

    def get_for_contract(self, contract_name: str) -> AICapabilityBinding | None:
        """Return one registered binding by contract name."""

        return self._contract_bindings.get(contract_name)

    def snapshot(self) -> AICapabilityBindingSnapshot:
        """Return an immutable read snapshot sorted by binding key."""

        bindings = tuple(self._bindings[key] for key in sorted(self._bindings))
        return AICapabilityBindingSnapshot(
            bindings=bindings,
            by_key=MappingProxyType(
                {binding.binding_key: binding for binding in bindings}
            ),
            by_contract=MappingProxyType(
                {binding.contract_name: binding for binding in bindings}
            ),
        )
