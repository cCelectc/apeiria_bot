"""Inventory for compatibility surfaces retired by migration work."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetiredCompatibilitySurface:
    """One runtime compatibility surface that should not accept new usage."""

    key: str
    category: str
    replacement: str


RETIRED_COMPATIBILITY_SURFACES: tuple[RetiredCompatibilitySurface, ...] = (
    RetiredCompatibilitySurface(
        key="root_bot_script",
        category="startup",
        replacement="apeiria run or python -m apeiria.bot.entry",
    ),
    RetiredCompatibilitySurface(
        key="bootstrap_facade",
        category="startup",
        replacement="apeiria.runtime.bootstrapper.ApeiriaBootstrapper",
    ),
    RetiredCompatibilitySurface(
        key="user_bot_nonebot_argument",
        category="local_setup",
        replacement="configure(driver)",
    ),
    RetiredCompatibilitySurface(
        key="web_ui_token_expire_days",
        category="config",
        replacement="[plugins.web_ui].token_expire_days",
    ),
    RetiredCompatibilitySurface(
        key="web_ui_auth_legacy_schema",
        category="auth_storage",
        replacement="current data/web_ui/secret.json account schema",
    ),
    RetiredCompatibilitySurface(
        key="plugin_config_flattening",
        category="plugin_config",
        replacement="[plugins.<section>] config tables",
    ),
)

NON_MIGRATION_COMPATIBILITY_TERMS: tuple[str, ...] = (
    "openai_compatible",
    "anthropic_compatible",
    "model_fallback_chain",
    "policy_fallback",
    "ui_default_fallback",
)


__all__ = [
    "NON_MIGRATION_COMPATIBILITY_TERMS",
    "RETIRED_COMPATIBILITY_SURFACES",
    "RetiredCompatibilitySurface",
]
