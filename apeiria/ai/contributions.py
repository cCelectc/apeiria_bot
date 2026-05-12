"""Plugin-facing AI contribution declarations.

Plugins that depend on ``apeiria.builtin_plugins.ai`` can import this module at
plugin import time to declare AI tools, file-based skill sources, and host-action
handlers. The declarations are stored in a narrow registry; the AI plugin
lifecycle applies them during startup.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from apeiria.ai.capabilities import (
    AICapabilityBinding,
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
    create_local_tool_binding,
)
from apeiria.ai.tools.schema import (
    build_json_schema,
    build_parameters_from_signature,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.ai.tools.models import AIToolResult, AIToolRiskLevel

    AIHostActionHandler = Callable[[dict[str, Any]], Any | Awaitable[Any]]
    AIToolHandler = Callable[..., Awaitable[AIToolResult]]


@dataclass(frozen=True)
class AIPluginHostActionHandlerContribution:
    """One plugin-contributed handler without a complete contract."""

    action_name: str
    handler: "AIHostActionHandler"


@dataclass(frozen=True)
class AIPluginCapabilityContractContribution:
    """One plugin-contributed capability contract declaration."""

    contract: AICapabilityContract


@dataclass(frozen=True)
class AIPluginHostActionContribution:
    """One complete plugin-contributed host action."""

    contract: AICapabilityContract
    handler: "AIHostActionHandler"


@dataclass(frozen=True)
class AIPluginToolContribution:
    """One plugin-declared local executable capability."""

    contract: AICapabilityContract
    binding: AICapabilityBinding


@dataclass(frozen=True)
class AIPluginSkillSource:
    """One plugin-contributed skill file or directory path."""

    path: Path


@dataclass(frozen=True)
class AIPluginContributionSnapshot:
    """Immutable snapshot consumed by the AI lifecycle coordinator."""

    tools: tuple[AIPluginToolContribution, ...] = ()
    capability_contracts: tuple[AIPluginCapabilityContractContribution, ...] = ()
    host_actions: tuple[AIPluginHostActionContribution, ...] = ()
    host_action_handlers: tuple[AIPluginHostActionHandlerContribution, ...] = ()
    skill_sources: tuple[AIPluginSkillSource, ...] = ()


@dataclass(frozen=True)
class AIPluginCapabilityContractInput:
    """Create payload for one plugin capability contract declaration."""

    name: str
    description: str
    input_schema: dict[str, Any] | None = None
    read_only: bool = True
    concurrency_safe: bool = True
    risk_level: AIToolRiskLevel = "low"
    timeout_seconds: float | None = None
    requires_operator_approval: bool = False
    tags: tuple[str, ...] = ()


class AIPluginContributionRegistry:
    """In-memory registry for plugin-declared AI startup contributions."""

    def __init__(self) -> None:
        self._tools: dict[str, AIPluginToolContribution] = {}
        self._capability_contracts: dict[
            str, AIPluginCapabilityContractContribution
        ] = {}
        self._host_actions: dict[str, AIPluginHostActionContribution] = {}
        self._host_action_handlers: dict[
            str, AIPluginHostActionHandlerContribution
        ] = {}
        self._skill_sources: dict[Path, AIPluginSkillSource] = {}

    def register_tool(
        self,
        *,
        contract: AICapabilityContract,
        binding: AICapabilityBinding,
    ) -> AIPluginToolContribution:
        """Declare one local executable capability for lifecycle registration."""

        contract = _as_plugin_contract(contract)
        binding = replace(binding, contract_name=contract.name)
        contribution = AIPluginToolContribution(
            contract=contract,
            binding=binding,
        )
        self._tools[contract.name] = contribution
        return contribution

    def register_capability_contract(
        self,
        contract: AICapabilityContract,
    ) -> AIPluginCapabilityContractContribution:
        """Declare a capability contract without binding it to a handler."""

        contribution = AIPluginCapabilityContractContribution(contract=contract)
        self._capability_contracts[contract.name] = contribution
        return contribution

    def register_host_action(
        self,
        *,
        contract: AICapabilityContract,
        handler: "AIHostActionHandler",
    ) -> AIPluginHostActionContribution:
        """Declare a complete host action with contract and handler."""

        contract = _as_plugin_contract(contract)
        contribution = AIPluginHostActionContribution(
            contract=contract,
            handler=handler,
        )
        self._host_actions[contract.name] = contribution
        self.register_capability_contract(contract)
        return contribution

    def register_host_action_handler(
        self,
        action_name: str,
        handler: "AIHostActionHandler",
    ) -> AIPluginHostActionHandlerContribution:
        """Declare one handler-only host action."""

        contribution = AIPluginHostActionHandlerContribution(
            action_name=action_name,
            handler=handler,
        )
        self._host_action_handlers[action_name] = contribution
        return contribution

    def register_skill_source(
        self,
        path: str | Path,
        *,
        base_path: str | Path | None = None,
    ) -> AIPluginSkillSource:
        """Declare a skill directory or ``SKILL.md`` file.

        Relative paths are resolved against ``base_path`` when supplied, or the
        current working directory for direct registry calls. Public helper
        functions below resolve omitted ``base_path`` values against the caller
        module directory.
        """

        resolved = _resolve_path(path, base_path=base_path)
        source = AIPluginSkillSource(path=resolved)
        self._skill_sources[resolved] = source
        return source

    def snapshot(self) -> AIPluginContributionSnapshot:
        """Return deterministic declarations without mutating the registry."""

        return AIPluginContributionSnapshot(
            tools=tuple(self._tools[name] for name in sorted(self._tools)),
            capability_contracts=tuple(
                self._capability_contracts[name]
                for name in sorted(self._capability_contracts)
            ),
            host_actions=tuple(
                self._host_actions[name] for name in sorted(self._host_actions)
            ),
            host_action_handlers=tuple(
                self._host_action_handlers[name]
                for name in sorted(self._host_action_handlers)
            ),
            skill_sources=tuple(
                self._skill_sources[path] for path in sorted(self._skill_sources)
            ),
        )


ai_plugin_contributions = AIPluginContributionRegistry()


def register_ai_tool(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    read_only: bool,
    concurrency_safe: bool,
    risk_level: "AIToolRiskLevel" = "low",
    timeout_seconds: float | None = None,
    requires_operator_approval: bool = False,
    tags: tuple[str, ...] = (),
) -> "Callable[[AIToolHandler], AIToolHandler]":
    """Decorator for plugin-declared local executable capabilities.

    The capability contract and binding are collected for the lifecycle
    coordinator rather than being inserted directly into the runtime singleton.
    """

    def decorator(func: "AIToolHandler") -> "AIToolHandler":
        parameters = build_parameters_from_signature(func)
        contract = AICapabilityContract(
            name=name,
            kind=AICapabilityKind.EXECUTABLE,
            origin=AICapabilityOrigin.PLUGIN,
            description=description,
            input_schema=build_json_schema(parameters) if parameters else {},
            safety=AICapabilitySafety(
                read_only=read_only,
                risk_level=risk_level,
                concurrency_safe=concurrency_safe,
                timeout_seconds=timeout_seconds,
                requires_operator_approval=requires_operator_approval,
            ),
            tags=tags,
        )
        binding = create_local_tool_binding(
            contract_name=contract.name,
            binding_key=f"plugin:{contract.name}",
            handler=func,
        )
        ai_plugin_contributions.register_tool(
            contract=contract,
            binding=binding,
        )
        func_with_metadata = cast("Any", func)
        func_with_metadata.__ai_tool_contract__ = contract
        func_with_metadata.__ai_tool_binding__ = binding
        return func

    return decorator


def register_ai_capability_contract(
    create_input: AIPluginCapabilityContractInput,
) -> AICapabilityContract:
    """Register a plugin-declared executable capability contract."""

    contract = AICapabilityContract(
        name=create_input.name,
        kind=AICapabilityKind.EXECUTABLE,
        origin=AICapabilityOrigin.PLUGIN,
        description=create_input.description,
        input_schema=create_input.input_schema or {},
        safety=AICapabilitySafety(
            read_only=create_input.read_only,
            risk_level=create_input.risk_level,
            concurrency_safe=create_input.concurrency_safe,
            timeout_seconds=create_input.timeout_seconds,
            requires_operator_approval=create_input.requires_operator_approval,
        ),
        tags=create_input.tags,
    )
    ai_plugin_contributions.register_capability_contract(contract)
    return contract


def register_ai_host_action(
    *,
    contract: AICapabilityContract,
    handler: "AIHostActionHandler",
) -> AIPluginHostActionContribution:
    """Register a complete plugin host action."""

    return ai_plugin_contributions.register_host_action(
        contract=contract,
        handler=handler,
    )


def register_ai_host_action_handler(
    action_name: str,
    handler: "AIHostActionHandler",
) -> AIPluginHostActionHandlerContribution:
    """Register a handler-only plugin host action for diagnostics."""

    return ai_plugin_contributions.register_host_action_handler(action_name, handler)


def register_ai_skill_source(
    path: str | Path,
    *,
    base_path: str | Path | None = None,
) -> Path:
    """Register a plugin skill directory or file and return its resolved path."""

    if base_path is None:
        base_path = _caller_directory()
    return ai_plugin_contributions.register_skill_source(
        path,
        base_path=base_path,
    ).path


def _resolve_path(
    path: str | Path,
    *,
    base_path: str | Path | None,
) -> Path:
    raw = Path(path).expanduser()
    if raw.is_absolute():
        return raw.resolve(strict=False)
    base = Path.cwd() if base_path is None else Path(base_path).expanduser()
    return (base / raw).resolve(strict=False)


def _caller_directory() -> Path:
    frame = inspect.currentframe()
    if frame is None:
        return Path.cwd()
    helper_frame = frame.f_back
    caller_frame = helper_frame.f_back if helper_frame is not None else None
    caller_file = (
        caller_frame.f_globals.get("__file__") if caller_frame is not None else None
    )
    if caller_file is None:
        return Path.cwd()
    return Path(str(caller_file)).resolve(strict=False).parent


def _as_plugin_contract(contract: AICapabilityContract) -> AICapabilityContract:
    if contract.origin is AICapabilityOrigin.PLUGIN:
        return contract
    return replace(contract, origin=AICapabilityOrigin.PLUGIN)


__all__ = [
    "AIPluginCapabilityContractContribution",
    "AIPluginCapabilityContractInput",
    "AIPluginContributionRegistry",
    "AIPluginContributionSnapshot",
    "AIPluginHostActionContribution",
    "AIPluginHostActionHandlerContribution",
    "AIPluginSkillSource",
    "AIPluginToolContribution",
    "ai_plugin_contributions",
    "register_ai_capability_contract",
    "register_ai_host_action",
    "register_ai_host_action_handler",
    "register_ai_skill_source",
    "register_ai_tool",
]
