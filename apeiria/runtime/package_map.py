"""Ownership map for Apeiria package bands."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ApeiriaPackageBand(str, Enum):
    """Repository ownership bands used by boundary checks."""

    INFRASTRUCTURE = "infrastructure"
    STABLE_ROOT = "stable_root"
    APP = "app"
    SURFACE = "surface"


@dataclass(frozen=True, slots=True)
class ApeiriaPackageRule:
    """A prefix rule that assigns a module path to one ownership band."""

    prefix: str
    band: ApeiriaPackageBand
    description: str


PACKAGE_RULES: tuple[ApeiriaPackageRule, ...] = (
    ApeiriaPackageRule(
        prefix="apeiria.config",
        band=ApeiriaPackageBand.INFRASTRUCTURE,
        description="Project configuration and settings loading.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.db",
        band=ApeiriaPackageBand.INFRASTRUCTURE,
        description="Database infrastructure and persistence primitives.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.environment",
        band=ApeiriaPackageBand.INFRASTRUCTURE,
        description="Project environment management and health checks.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.i18n",
        band=ApeiriaPackageBand.INFRASTRUCTURE,
        description="Translation and localization helpers.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.runtime",
        band=ApeiriaPackageBand.INFRASTRUCTURE,
        description="Runtime composition root and bootstrap phases.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.utils",
        band=ApeiriaPackageBand.INFRASTRUCTURE,
        description="Generic utility helpers.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.conversation",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Canonical conversation identity and persistence.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.access",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Access policy, repositories, and runtime permissions.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.plugins",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Plugin governance, metadata, and lifecycle core.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.model",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable AI model routing and source bindings.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.memory",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable AI memory storage and retrieval behavior.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.person",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable person profile domain behavior.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.persona",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable persona domain behavior.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.relationship",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable relationship modeling behavior.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.skills",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable AI skill catalog and runtime contracts.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.ai.tools",
        band=ApeiriaPackageBand.STABLE_ROOT,
        description="Reusable tool execution, policy, and registry behavior.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.app",
        band=ApeiriaPackageBand.APP,
        description="Application-owned orchestration namespaces.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.bot",
        band=ApeiriaPackageBand.SURFACE,
        description="NoneBot-facing delivery surface.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.builtin_plugins",
        band=ApeiriaPackageBand.SURFACE,
        description="Built-in plugin delivery surface.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.cli",
        band=ApeiriaPackageBand.SURFACE,
        description="CLI delivery surface.",
    ),
    ApeiriaPackageRule(
        prefix="apeiria.webui",
        band=ApeiriaPackageBand.SURFACE,
        description="FastAPI and Web UI delivery surface.",
    ),
)

INFRASTRUCTURE_PREFIXES: tuple[str, ...] = tuple(
    rule.prefix
    for rule in PACKAGE_RULES
    if rule.band == ApeiriaPackageBand.INFRASTRUCTURE
)
STABLE_ROOT_PREFIXES: tuple[str, ...] = tuple(
    rule.prefix for rule in PACKAGE_RULES if rule.band == ApeiriaPackageBand.STABLE_ROOT
)
APP_PREFIXES: tuple[str, ...] = tuple(
    rule.prefix for rule in PACKAGE_RULES if rule.band == ApeiriaPackageBand.APP
)
SURFACE_PREFIXES: tuple[str, ...] = tuple(
    rule.prefix for rule in PACKAGE_RULES if rule.band == ApeiriaPackageBand.SURFACE
)

# This stays available for migration batches that temporarily need exclusions,
# but the current tree no longer carries any app-owned stable-root subpackages.
STABLE_ROOT_BOUNDARY_EXCLUSIONS: tuple[str, ...] = ()

RETIRED_APP_OWNED_NAMESPACE_PREFIXES: tuple[str, ...] = (
    "apeiria.ai.admin",
    "apeiria.ai.conversation",
    "apeiria.ai.future_task",
    "apeiria.ai.pipeline",
    "apeiria.ai.reply_strategy",
    "apeiria.ai.session_read",
    "apeiria.chat",
    "apeiria.plugins.store",
    "apeiria.access.webui_auth",
)


def _matches_prefix(module_name: str, prefix: str) -> bool:
    return module_name == prefix or module_name.startswith(prefix + ".")


def classify_package(module_name: str) -> ApeiriaPackageRule | None:
    """Return the ownership rule for a module path, if one exists."""

    for rule in PACKAGE_RULES:
        if _matches_prefix(module_name, rule.prefix):
            return rule
    return None


def iter_package_rules() -> tuple[ApeiriaPackageRule, ...]:
    """Expose the package rules as an immutable tuple for tests/docs."""

    return PACKAGE_RULES


__all__ = [
    "APP_PREFIXES",
    "INFRASTRUCTURE_PREFIXES",
    "PACKAGE_RULES",
    "RETIRED_APP_OWNED_NAMESPACE_PREFIXES",
    "STABLE_ROOT_BOUNDARY_EXCLUSIONS",
    "STABLE_ROOT_PREFIXES",
    "SURFACE_PREFIXES",
    "ApeiriaPackageBand",
    "ApeiriaPackageRule",
    "classify_package",
    "iter_package_rules",
]
